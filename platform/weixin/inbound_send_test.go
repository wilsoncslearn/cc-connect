package weixin

import (
	"context"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"

	"github.com/chenhg5/cc-connect/core"
)

// The engine delivers ordinary agent responses through Platform.Send, not Reply.
// Exercise real inbound contexts (including image-only messages), not a manually
// selected sendPathReply, so this catches the incomplete #1742 fix.
func TestInboundSend_BypassesPushBudget(t *testing.T) {
	for _, image := range []bool{false, true} {
		name := "text"
		if image {
			name = "image"
		}
		t.Run(name, func(t *testing.T) {
			var sends atomic.Int32
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path == "/download" {
					_, _ = w.Write([]byte{0x89, 'P', 'N', 'G', '\r', '\n', 0x1a, '\n'})
					return
				}
				if r.URL.Path == "/ilink/bot/sendmessage" {
					sends.Add(1)
				}
				w.Header().Set("Content-Type", "application/json")
				_, _ = w.Write([]byte(`{"ret":0}`))
			}))
			defer srv.Close()
			p := &Platform{
				allowFrom: "*", httpClient: srv.Client(), cdnHttpClient: srv.Client(), cdnBaseURL: srv.URL,
				tokens:         map[string]string{"peer": "token"},
				sendQuotaLimit: 1, sendQuotaWindow: time.Hour,
			}
			p.api = newAPIClient(srv.URL, "test-token", "", srv.Client())
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			pushCtx, err := p.ReconstructReplyCtx(sessionKeyPrefix + "peer")
			if err != nil {
				t.Fatal(err)
			}
			if err := p.Send(ctx, pushCtx, "scheduled push"); err != nil {
				t.Fatal(err)
			}
			items := []messageItem{{Type: messageItemText, TextItem: &textItem{Text: "hello"}}}
			if image {
				items = []messageItem{{Type: messageItemImage, ImageItem: &imageItem{Media: &cdnMedia{EncryptQueryParam: "image-ref"}}}}
			}
			handled := 0
			for i := 0; i < 6; i++ {
				p.dispatchInbound(ctx, &weixinMessage{FromUserID: "peer", MessageType: messageTypeUser, MessageID: int64(i + 1), ItemList: items}, func(platform core.Platform, msg *core.Message) {
					handled++
					if image && len(msg.Images) != 1 {
						t.Fatal("image was not delivered to handler")
					}
					if err := platform.Send(ctx, msg.ReplyCtx, "agent response"); err != nil {
						t.Fatalf("inbound %s response blocked at turn %d: %v", name, i+1, err)
					}
				})
			}
			if handled != 6 || sends.Load() != 7 {
				t.Fatalf("handled=%d sends=%d; want 6 and 7", handled, sends.Load())
			}
			if err := p.Send(ctx, pushCtx, "another scheduled push"); err == nil {
				t.Fatal("proactive push bypassed quota")
			}
			if sends.Load() != 7 {
				t.Fatal("over-budget push reached API")
			}
		})
	}
}
