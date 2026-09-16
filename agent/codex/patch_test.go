package codex

import (
	"database/sql"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestPatchSessionSource(t *testing.T) {
	tmpDir := t.TempDir()

	sessionID := "test-session-abc123"
	sessionsDir := filepath.Join(tmpDir, ".codex", "sessions")
	if err := os.MkdirAll(sessionsDir, 0o755); err != nil {
		t.Fatal(err)
	}

	fname := filepath.Join(sessionsDir, "rollout-"+sessionID+".jsonl")
	line1 := `{"timestamp":"2026-01-01T00:00:00Z","type":"session_meta","payload":{"id":"` + sessionID + `","source":"exec","originator":"codex_exec","cwd":"/tmp"}}`
	line2 := `{"timestamp":"2026-01-01T00:00:01Z","type":"response_item","payload":{"role":"user"}}`
	content := line1 + "\n" + line2 + "\n"

	if err := os.WriteFile(fname, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}

	codexHome := filepath.Join(tmpDir, ".codex")

	patchSessionSource(sessionID, codexHome)

	data, err := os.ReadFile(fname)
	if err != nil {
		t.Fatal(err)
	}

	lines := strings.SplitN(string(data), "\n", 2)

	if !strings.Contains(lines[0], `"source":"cli"`) {
		t.Errorf("expected source:cli, got first line: %s", lines[0])
	}
	if !strings.Contains(lines[0], `"originator":"codex_cli_rs"`) {
		t.Errorf("expected originator:codex_cli_rs, got first line: %s", lines[0])
	}
	if strings.Contains(lines[0], `"source":"exec"`) {
		t.Error("source:exec was not replaced")
	}

	// Second line should be untouched
	if !strings.HasPrefix(lines[1], `{"timestamp":"2026-01-01T00:00:01Z"`) {
		t.Errorf("second line was corrupted: %s", lines[1])
	}
}

func TestPatchSessionSource_Idempotent(t *testing.T) {
	tmpDir := t.TempDir()
	sessionID := "test-idempotent-xyz"
	sessionsDir := filepath.Join(tmpDir, ".codex", "sessions")
	os.MkdirAll(sessionsDir, 0o755)

	fname := filepath.Join(sessionsDir, "rollout-"+sessionID+".jsonl")
	line1 := `{"type":"session_meta","payload":{"id":"` + sessionID + `","source":"cli","originator":"codex_cli_rs"}}`
	if err := os.WriteFile(fname, []byte(line1+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	codexHome := filepath.Join(tmpDir, ".codex")

	patchSessionSource(sessionID, codexHome)

	data, _ := os.ReadFile(fname)
	if string(data) != line1+"\n" {
		t.Errorf("file was modified when it shouldn't have been")
	}
}

func TestPatchSessionSourceUpdatesDesktopIndex(t *testing.T) {
	home := t.TempDir()
	db, err := sql.Open("sqlite", filepath.Join(home, "state_5.sqlite"))
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if _, err := db.Exec(`CREATE TABLE threads (id TEXT PRIMARY KEY, source TEXT, name TEXT);
		INSERT INTO threads VALUES ('mobile', 'exec', 'keep title'), ('other', 'exec', 'other title');`); err != nil {
		t.Fatal(err)
	}
	// A paginated rollout must stay byte-identical: its database stores byte offsets.
	os.MkdirAll(filepath.Join(home, "sessions"), 0755)
	if err := os.WriteFile(filepath.Join(home, "sessions", "rollout-mobile.jsonl"), []byte(`{"type":"session_meta","payload":{"id":"mobile","source":"exec","originator":"codex_exec"}}`+"\n"), 0644); err != nil {
		t.Fatal(err)
	}
	before, _ := os.ReadFile(filepath.Join(home, "sessions", "rollout-mobile.jsonl"))
	for i := 0; i < 2; i++ {
		patchSessionSource("mobile", home)
	}
	after, _ := os.ReadFile(filepath.Join(home, "sessions", "rollout-mobile.jsonl"))
	if string(before) != string(after) {
		t.Fatal("indexed rollout byte offsets were changed")
	}
	var source, name string
	if err := db.QueryRow("SELECT source, name FROM threads WHERE id = 'mobile'").Scan(&source, &name); err != nil {
		t.Fatal(err)
	}
	if source != "cli" || name != "keep title" {
		t.Fatalf("unexpected target row: %s %s", source, name)
	}
	if err := db.QueryRow("SELECT source FROM threads WHERE id = 'other'").Scan(&source); err != nil {
		t.Fatal(err)
	}
	if source != "exec" {
		t.Fatal("unrelated session was changed")
	}
}
