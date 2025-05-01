import '../styles/globals.css';
import Head from 'next/head';

function MyApp({ Component, pageProps }) {
    return (
        <>
            <Head>
                <title>Tax Calculator for Trading212</title>
                <meta name="description" content="Calculate your taxes for Trading212 and other brokers" />
                <link rel="icon" href="/favicon.ico" />
            </Head>
            <Component {...pageProps} />
        </>
    );
}

export default MyApp;