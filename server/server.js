import express from 'express';
import cors from 'cors';
import questionnaireRoutes from './routes/questionnaire.js';

const app = express();
app.use(cors());
app.use(express.json());

app.use('/api/questionnaire', questionnaireRoutes);

app.listen(3001, () => {
  console.log('Server running at http://localhost:3001');
});