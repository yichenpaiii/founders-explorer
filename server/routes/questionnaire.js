import express from 'express';
import db from '../db/index.js';

const router = express.Router();

router.post('/', async (req, res) => {
  const { name, age, feedback } = req.body;
  try {
    await db.saveQuestionnaire({ name, age, feedback });
    res.json({ message: '数据已暂存（内存版）' });
  } catch (err) {
    res.status(500).json({ error: '保存失败' });
  }
});

router.get('/', async (req, res) => {
  const data = await db.getAllQuestionnaires();
  res.json(data);
});

export default router;