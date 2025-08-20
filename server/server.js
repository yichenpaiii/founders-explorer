require('dotenv').config();
const express = require('express');
const cors = require('cors');

const app = express();
// allow Vite to call this API from the browser
// in production, make this origin configurable via an env var
app.use(cors({ origin: 'http://localhost:5173' }));
app.use(express.json());

// Routes
const courseRoutes = require('./routes/courses');
app.use('/api/courses', courseRoutes);

// Picks the port from env (PORT) or falls back to 3000
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`API: http://localhost:${PORT}`));