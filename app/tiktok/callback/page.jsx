// TikTok sends the team member back here after they allow BTR Studio. The page only shows the one-time code, which
// they paste into the BTR Studio bot on Telegram (the bot exchanges it; nothing is stored here). Never linked.
import Code from './Code';

export const metadata = { title: 'BTR Studio · TikTok', robots: { index: false, follow: false } };

export default function TikTokCallback() {
  return <Code />;
}
