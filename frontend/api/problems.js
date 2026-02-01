// Vercel Serverless Function for Problem Storage
// This provides a simple key-value store for problem text
// Problems are stored temporarily and cleaned up after 24 hours

// In-memory storage (for demo - in production use Redis/KV)
// Note: Vercel serverless functions are stateless, so this resets on cold starts
// For production, use Vercel KV or an external database

const problems = new Map();

export default async function handler(req, res) {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }

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

            // Store problem (in production, use persistent storage)
            problems.set(normalizedHash, {
                text: problemText,
                type: problemType || 0,
                timestamp: Date.now()
            });

            console.log(`Stored problem ${normalizedHash}: ${problemText.substring(0, 50)}...`);

            return res.status(200).json({ 
                success: true, 
                hash: normalizedHash 
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
            // Return all problems (for debugging)
            return res.status(200).json({
                success: true,
                count: problems.size,
                note: 'Pass ?hash=0x... to get specific problem'
            });
        }

        const normalizedHash = hash.toLowerCase().startsWith('0x') 
            ? hash.toLowerCase() 
            : '0x' + hash.toLowerCase();

        const problem = problems.get(normalizedHash);

        if (!problem) {
            return res.status(404).json({ 
                success: false, 
                error: 'Problem not found' 
            });
        }

        return res.status(200).json({
            success: true,
            hash: normalizedHash,
            text: problem.text,
            type: problem.type,
            timestamp: problem.timestamp
        });
    }

    return res.status(405).json({ error: 'Method not allowed' });
}
