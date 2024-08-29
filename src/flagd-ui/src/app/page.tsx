"use client";
import { useEffect, useState } from "react";
import FeatureFlag from "./components/FeatureFlag";
import Link from "next/link";

export default function Home() {
  const [flagData, setflagData] = useState<any>(null);
  const [reloadData, setreloadData] = useState(false);
  useEffect(() => {
    const readFile = () => {
      const fileContent = fetch("/api/read-file", {
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
    readFile();
    if (reloadData) {
      setreloadData(false);
    }
  }, [reloadData]);

  return (
    <div className="app">
      <Link href="/advanced" passHref>
        <button
          style={{ padding: "10px 20px", fontSize: "16px", cursor: "pointer" }}
        >
          Advanced
        </button>
      </Link>
      {flagData &&
        Object.keys(flagData.flags).map((flagId) => {
          const flagConfig: FlagConfig = flagData.flags[flagId];
          return (
            <FeatureFlag
              flagId={flagId}
              key={flagId}
              setreloadData={setreloadData}
              flagConfig={flagConfig}
              configFile={flagData}
            />
          );
        })}
    </div>
  );
}
