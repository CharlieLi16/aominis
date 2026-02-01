// Vercel Serverless Function for Problem Storage
// Uses Vercel KV (Redis) for persistent storage
// Problems are stored with 7 day TTL

import { kv } from '@vercel/kv';

// Fallback in-memory storage if KV is not configured
const memoryStore = new Map();

async function getStorage() {
    // Check if KV is configured
    if (process.env.KV_REST_API_URL && process.env.KV_REST_API_TOKEN) {
        return {
            get: async (key) => await kv.get(key),
            set: async (key, value, ttl) => await kv.set(key, value, { ex: ttl }),
            type: 'kv'
        };
    }
    // Fallback to memory (will lose data on cold start)
    return {
        get: async (key) => memoryStore.get(key),
        set: async (key, value) => memoryStore.set(key, value),
        type: 'memory'
    };
}

export default async function handler(req, res) {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }

    const storage = await getStorage();
    const { hash } = req.query;

    // POST /api/problems - Store a problem
    if (req.method === 'POST') {
        try {
            const { problemHash, problemText, problemType } = req.body;
            
            if (!problemHash || !problemText) {
                return res.status(400).json({ 
                    success: false, 
                    error: 'problemHash and problemText required' 
                });
            }

            // Normalize hash
            const normalizedHash = problemHash.toLowerCase().startsWith('0x') 
                ? problemHash.toLowerCase() 
                : '0x' + problemHash.toLowerCase();

            const problemData = {
                text: problemText,
                type: problemType || 0,
                timestamp: Date.now()
            };

            // Store problem with 7 day TTL (604800 seconds)
            const key = `problem:${normalizedHash}`;
            await storage.set(key, problemData, 604800);

            console.log(`[${storage.type}] Stored problem ${normalizedHash}: ${problemText.substring(0, 50)}...`);

            return res.status(200).json({ 
                success: true, 
                hash: normalizedHash,
                storage: storage.type
            });
        } catch (error) {
            console.error('Error storing problem:', error);
            return res.status(500).json({ 
                success: false, 
                error: error.message 
            });
        }
    }

    // GET /api/problems?hash=0x... - Retrieve a problem
    if (req.method === 'GET') {
        if (!hash) {
            return res.status(200).json({
                success: true,
                storage: storage.type,
                note: 'Pass ?hash=0x... to get specific problem'
            });
        }

        try {
            const normalizedHash = hash.toLowerCase().startsWith('0x') 
                ? hash.toLowerCase() 
                : '0x' + hash.toLowerCase();

            const key = `problem:${normalizedHash}`;
            const problem = await storage.get(key);

            if (!problem) {
                return res.status(404).json({ 
                    success: false, 
                    error: 'Problem not found',
                    storage: storage.type
                });
            }

            return res.status(200).json({
                success: true,
                hash: normalizedHash,
                text: problem.text,
                type: problem.type,
                timestamp: problem.timestamp
            });
        } catch (error) {
            console.error('Error fetching problem:', error);
            return res.status(500).json({ 
                success: false, 
                error: error.message 
            });
        }
    }

    return res.status(405).json({ error: 'Method not allowed' });
}
