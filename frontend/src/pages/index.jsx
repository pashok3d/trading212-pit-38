import { useEffect } from 'react';
import { useRouter } from 'next/router';

// Redirect to import page from the root URL
export default function Home() {
    const router = useRouter();

    useEffect(() => {
        router.push('/import');
    }, [router]);

    return null;
}
