import React, { useState } from 'react';
import Layout from '../components/Layout';
import { uploadCSV } from '../services/api';

// File drop zone component
const FileDropZone = ({ title, onFileSelect, isUploading }) => {
    const [isDragging, setIsDragging] = useState(false);

    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = () => {
        setIsDragging(false);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragging(false);

        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            onFileSelect(e.dataTransfer.files[0]);
        }
    };

    const handleFileSelect = (e) => {
        if (e.target.files && e.target.files.length > 0) {
            onFileSelect(e.target.files[0]);
        }
    };

    return (
        <div
            className={`rounded-lg p-6 flex flex-col items-center justify-center border-2 border-dashed cursor-pointer h-60
        ${isDragging ? 'border-primary-500 bg-primary-50' : 'border-primary-300 bg-primary-100 hover:bg-primary-50'}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            <h3 className="text-xl font-semibold mb-2">{title}</h3>
            <p className="text-center text-sm text-gray-600 mb-4">
                Drag &amp; drop or click to upload your CSV file
            </p>

            <input
                type="file"
                accept=".csv"
                className="hidden"
                id={`file-upload-${title}`}
                onChange={handleFileSelect}
            />

            <label
                htmlFor={`file-upload-${title}`}
                className="px-4 py-2 bg-primary-500 text-white rounded hover:bg-primary-600 cursor-pointer"
            >
                {isUploading ? 'Uploading...' : 'Select File'}
            </label>
        </div>
    );
};

export default function ImportPage() {
    const [isUploading, setIsUploading] = useState(false);
    const [uploadResult, setUploadResult] = useState(null);
    const [error, setError] = useState(null);

    const handleFileSelect = async (file) => {
        setIsUploading(true);
        setError(null);

        try {
            const result = await uploadCSV(file);
            setUploadResult(result);
            console.log('Upload success:', result);
        } catch (err) {
            console.error('Upload error:', err);
            setError(err.message || 'Failed to upload file');
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <Layout>
            <div className="p-6">
                <h2 className="text-2xl font-semibold mb-6">Import Transactions</h2>

                {error && (
                    <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
                        {error}
                    </div>
                )}

                {uploadResult && (
                    <div className="mb-6 p-4 bg-green-100 border border-green-400 text-green-700 rounded">
                        Successfully uploaded! Found {uploadResult.transaction_count} transactions.
                    </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <FileDropZone
                        title="Trading212"
                        onFileSelect={handleFileSelect}
                        isUploading={isUploading}
                    />

                    <FileDropZone
                        title="Other Broker"
                        onFileSelect={handleFileSelect}
                        isUploading={isUploading}
                    />
                </div>

                <div className="mt-8">
                    <h3 className="text-xl font-semibold mb-4">Import Instructions</h3>
                    <div className="bg-white rounded-lg shadow p-4">
                        <h4 className="font-medium mb-2">Trading212</h4>
                        <ol className="list-decimal ml-5 space-y-2">
                            <li>Log in to your Trading212 account</li>
                            <li>Go to History section and select the date range</li>
                            <li>Click on "Export" button and download the CSV file</li>
                            <li>Upload the CSV file here</li>
                        </ol>

                        <h4 className="font-medium mt-4 mb-2">Other Brokers</h4>
                        <p>
                            Make sure your CSV file has the following columns:
                        </p>
                        <ul className="list-disc ml-5 mt-2 space-y-1">
                            <li>Time - transaction date and time</li>
                            <li>Action - type of transaction (Market buy, Market sell, Dividend, etc.)</li>
                            <li>Ticker - stock symbol</li>
                            <li>Name - stock name (optional)</li>
                            <li>No. of shares - quantity</li>
                            <li>Price / share - price per share</li>
                            <li>Currency - currency of the transaction</li>
                            <li>Total - total transaction amount</li>
                        </ul>
                    </div>
                </div>
            </div>
        </Layout>
    );
}