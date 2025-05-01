import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';

const NavItem = ({ href, title, icon, count, isActive }) => (
    <Link
        href={href}
        className={`flex items-center px-4 py-2 text-sm rounded-md ${isActive ? 'bg-primary-100 text-primary-700' : 'text-gray-700 hover:bg-gray-100'
            }`}
    >
        {icon}
        <span className="ml-3">{title}</span>
        {count && (
            <span className="ml-auto bg-gray-200 text-gray-700 px-2 py-0.5 rounded text-xs">
                {count}
            </span>
        )}
    </Link>
);

export default function Layout({ children }) {
    const router = useRouter();

    // Simulated counts - in a real app, you'd get these from your API
    const counts = {
        fifo: 115,
        transactions: 605,
        openPositions: 19,
        dividends: 392
    };

    return (
        <div className="flex h-screen bg-gray-50">
            {/* Sidebar */}
            <div className="w-64 bg-white border-r">
                <div className="p-4 border-b">
                    <h1 className="text-xl font-semibold text-primary-600">TaxCalc</h1>
                </div>

                <nav className="p-4">
                    <div className="space-y-1">
                        <NavItem
                            href="/import"
                            title="Import"
                            icon={
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                                </svg>
                            }
                            isActive={router.pathname === '/import'}
                        />

                        <div className="pl-4 mt-3 mb-1">
                            <h3 className="font-medium text-xs uppercase text-gray-500 tracking-wider">Stocks</h3>
                        </div>

                        <NavItem
                            href="/fifo"
                            title="FIFO"
                            icon={
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                </svg>
                            }
                            count={counts.fifo}
                            isActive={router.pathname === '/fifo'}
                        />

                        <NavItem
                            href="/transactions"
                            title="Transactions"
                            icon={
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                                </svg>
                            }
                            count={counts.transactions}
                            isActive={router.pathname === '/transactions'}
                        />

                        <NavItem
                            href="/open-positions"
                            title="Open Positions"
                            icon={
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                                </svg>
                            }
                            count={counts.openPositions}
                            isActive={router.pathname === '/open-positions'}
                        />

                        <NavItem
                            href="/dividends"
                            title="Dividends"
                            icon={
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                            }
                            count={counts.dividends}
                            isActive={router.pathname === '/dividends'}
                        />

                        <NavItem
                            href="/summary"
                            title="Summary"
                            icon={
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                </svg>
                            }
                            isActive={router.pathname === '/summary'}
                        />
                    </div>
                </nav>
            </div>

            {/* Main Content */}
            <div className="flex-1 overflow-auto">
                {children}
            </div>
        </div>
    );
}