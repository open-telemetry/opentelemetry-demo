import fs from "fs";
import path from "path";
import { isUtf8 } from "buffer";
import type { NextApiResponse, NextApiRequest } from "next";

export default function handler(
  req: NextApiRequest,
  res: NextApiResponse<any>
) {
  if (req.method === "POST") {
    const { data } = req.body;
    const filePath = path.join(process.cwd(), "data", "output.json");
    fs.writeFile(filePath, JSON.stringify(data, null, 2), (err) => {
      if (err) {
        res.status(500).json({ message: "Error writing to file" });
        return;
      }
      res.status(200).json({ message: "File written successfully" });
    });
  } else {
    res.status(405).json({ message: "Method not allowed" });
  }
}
