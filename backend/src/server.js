import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import apiRouter from "./routes/api.js";

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

app.use(
  cors({
    origin: process.env.CORS_ORIGIN || "http://localhost:5173"
  })
);
app.use(express.json());

app.use("/api/v1", apiRouter);

app.listen(PORT, () => {
  console.log(`[Samudera Jaya Backend] berjalan di http://localhost:${PORT}/api/v1`);
});
