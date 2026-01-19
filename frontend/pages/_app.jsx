import "../styles/globals.css";
import Head from "next/head";
import { useEffect } from "react";

export default function MyApp({ Component, pageProps }) {
  useEffect(() => {
    const theme = document.documentElement.style;
    theme.setProperty("color-scheme", "dark");
  }, []);

  return (
    <>
      <Head>
        <title>Apollo Email Intelligence</title>
        <link
          rel="icon"
          href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><defs><linearGradient id='g' x1='0%' y1='0%' x2='100%' y2='100%'><stop stop-color='%237c5dff' offset='0%'/><stop stop-color='%2325d0a6' offset='100%'/></linearGradient></defs><rect width='64' height='64' rx='14' fill='url(%23g)'/><path fill='%230a0d14' d='M18 42l6-20h6l6 20h-6l-1-4h-5l-1 4h-5zm9-8h3l-1.5-6.2z'/></svg>"
        />
      </Head>
      <div className="app-shell">
        <div className="glow purple" />
        <div className="glow green" />
        <Component {...pageProps} />
      </div>
    </>
  );
}
