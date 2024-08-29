"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import FileEditor from "../src/app/components/FileEditor";

export default function Home() {
  const [flagData, setflagData] = useState(null);
  const [reloadData, setreloadData] = useState(false);
  useEffect(() => {
    const readFile = (file_name: string) => {
      const fileContent = fetch(`/api/read-file?${file_name}`, {
        method: "GET",
        headers: { "Content-Type": "application/json" },
      })
        .then((response) => response.json())
        .then((data) => {
          setflagData(data);
          console.log(data);
        })
        .catch((error) => console.error(error));
    };

    // Initial read
    readFile("");
    if (reloadData) {
      setreloadData(false);
    }
  }, [reloadData]);
  return (
    <div className="app">
      <Link href="/" passHref>
        <button
          style={{ padding: "10px 20px", fontSize: "16px", cursor: "pointer" }}
        >
          Basic
        </button>
      </Link>
      <FileEditor setreloadData={setreloadData} flagConfig={flagData} />
    </div>
  );
}
