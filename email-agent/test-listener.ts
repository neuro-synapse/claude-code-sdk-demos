// Test script to manually trigger listener
import { ListenersManager } from "./ccsdk/listeners-manager";
import { ImapManager } from "./database/imap-manager";
import { DatabaseManager } from "./database/database-manager";
import type { Email } from "./agent/custom_scripts/types";

async function testListener() {
  console.log("🧪 Testing listener execution...\n");

  // Get manager instances
  const imapManager = ImapManager.getInstance();
  const dbManager = DatabaseManager.getInstance();

  // Create listeners manager
  const listenersManager = new ListenersManager(
    (notification) => {
      console.log("\n📬 Listener Notification:", notification);
    },
    imapManager,
    dbManager
  );

  // Load listeners
  await listenersManager.loadAllListeners();
  console.log("✓ Listeners loaded\n");

  // Create a test email
  const testEmail: Email = {
    messageId: "<test-email@example.com>",
    from: "example@example.com",
    to: "recipient@example.com",
    subject: "Important Test Email",
    body: "This is an important test message to trigger the listener.",
    date: new Date().toISOString(),
    isRead: false,
    hasAttachments: false,
    labels: [],
    uid: 12345
  };

  console.log("📧 Test Email:");
  console.log(JSON.stringify(testEmail, null, 2));
  console.log("\n🔥 Triggering email_received event...\n");

  // Trigger the event
  await listenersManager.checkEvent("email_received", testEmail);

  console.log("\n✅ Test complete!");
}

testListener().catch(console.error);
