import fs from "fs";
import path from "path";
// import data_file from "../../../flagd/demo.flagd.json";
import type { NextApiResponse, NextApiRequest } from "next";
import { isUtf8 } from "buffer";

export default function handler(
  req: NextApiRequest,
  res: NextApiResponse<any>
) {
  const file_name = req.query.file_name?.toString() || "output.json";
  if (req.method === "GET") {
    const data = JSON.parse(
      fs.readFileSync(path.join(process.cwd(), "data", file_name), {
        encoding: "utf8",
        flag: "r",
      })
    );
    res.status(200).json(data);
  } else {
    res.status(405).json({ message: "Method not allowed" });
  }
}
export function readFileContents(file_name: string) {
  fetch(`/api/read-file?${file_name}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  })
    .then((response) => response.json())
    .then((data) => data);
}
