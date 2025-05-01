const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Upload CSV files to the backend
 * @param {File} file - The CSV file to upload
 * @returns {Promise} - Response from the API
 */
export async function uploadCSV(file) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_URL}/api/upload`, {
        method: 'POST',
        body: formData,
    });

    if (!response.ok) {
        throw new Error('Upload failed');
    }

    return response.json();
}

/**
 * Get FIFO calculations from the backend
 * @param {number} year - Optional year filter
 * @returns {Promise} - Response from the API with FIFO data
 */
export async function getFIFO(year = null) {
    const url = new URL(`${API_URL}/api/fifo`);
    if (year) {
        url.searchParams.append('year', year);
    }

    const response = await fetch(url);

    if (!response.ok) {
        throw new Error('Failed to fetch FIFO data');
    }

    return response.json();
}

/**
 * Get transactions from the backend
 * @param {Object} filters - Optional filters for the transactions
 * @returns {Promise} - Response from the API with transaction data
 */
export async function getTransactions(filters = {}) {
    const url = new URL(`${API_URL}/api/transactions`);

    // Add filters as query parameters
    Object.entries(filters).forEach(([key, value]) => {
        if (value !== null && value !== undefined) {
            url.searchParams.append(key, value);
        }
    });

    const response = await fetch(url);

    if (!response.ok) {
        throw new Error('Failed to fetch transactions');
    }

    return response.json();
}

/**
 * Get tax summary from the backend
 * @param {number} year - The year to get summary for
 * @returns {Promise} - Response from the API with summary data
 */
export async function getTaxSummary(year) {
    const response = await fetch(`${API_URL}/api/summary/${year}`);

    if (!response.ok) {
        throw new Error('Failed to fetch tax summary');
    }

    return response.json();
}

/**
 * Get dividend data from the backend
 * @param {number} year - Optional year filter
 * @returns {Promise} - Response from the API with dividend data
 */
export async function getDividends(year = null) {
    const url = new URL(`${API_URL}/api/dividends`);
    if (year) {
        url.searchParams.append('year', year);
    }

    const response = await fetch(url);

    if (!response.ok) {
        throw new Error('Failed to fetch dividend data');
    }

    return response.json();
}

/**
 * Get current holdings (open positions) from the backend
 * @returns {Promise} - Response from the API with current holdings
 */
export async function getCurrentHoldings() {
    const response = await fetch(`${API_URL}/api/holdings`);

    if (!response.ok) {
        throw new Error('Failed to fetch current holdings');
    }

    return response.json();
}