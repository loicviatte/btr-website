import './globals.css';
import './dc.generated.css';
import MediaLightbox from '../components/MediaLightbox';

export const metadata = {
  title: 'Break The Routine · The DanceSport Podcast',
  description: 'Long conversations with the judges, dancers and decision-makers of DanceSport. New episode every Tuesday on YouTube, Spotify, Instagram and TikTok.',
  metadataBase: new URL(process.env.SITE_URL || 'https://breaktheroutine.vercel.app'),
  openGraph: { siteName: 'Break The Routine', type: 'website', images: ['/assets/6704faaedd6251c16887bc9024d7381e.jpg'] },
  icons: { icon: '/assets/745152d7135187f4378802fc563253b5.png' },
  // Hidden from Google until launch: set SITE_LIVE=1 in Vercel to open it up.
  robots: process.env.SITE_LIVE === '1' ? { index: true, follow: true } : { index: false, follow: false },
};

export const viewport = { themeColor: '#080403', width: 'device-width', initialScale: 1 };

export default function RootLayout({ children }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..700&display=swap" />
        <script dangerouslySetInnerHTML={{ __html: "window.__btrAskApi='/api/ask'" }} />
        {process.env.ANTHROPIC_API_KEY ? <script dangerouslySetInnerHTML={{ __html: "window.__btrSearchApi='/api/search'" }} /> : null}
        <script
          dangerouslySetInnerHTML={{
            __html: "try{if(sessionStorage.getItem('btr-intro')==='1')document.documentElement.classList.add('btr-seen')}catch(e){}",
          }}
        />
      </head>
      <body>
        {children}
        <MediaLightbox />
      </body>
    </html>
  );
}
