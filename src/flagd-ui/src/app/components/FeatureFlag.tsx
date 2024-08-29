"use client";
import "./FeatureFlag.css";
import React, { useCallback } from "react";
import { useState } from "react";

type FeatureFlagsProps = {
  flagId: string;
  setreloadData: (param: boolean) => void;
  flagConfig: FlagConfig;
  configFile?: ConfigFile;
};

function FeatureFlag({
  flagId,
  setreloadData,
  flagConfig,
  configFile,
}: FeatureFlagsProps) {
  const [enableDisable, setEnableDisable] = useState(
    flagConfig.state === "ENABLED"
  );
  const [toggleOn, setToggleOn] = useState(flagConfig.defaultVariant === "on"); // TODO adopt this
  const enableDisableMapping = {
    on: true,
    off: false,
  };

  const handleEnableDisableChange = useCallback(
    (e: {
      target: { checked: boolean | ((prevState: boolean) => boolean) };
    }) => {
      setEnableDisable(e.target.checked);
    },
    []
  );

  const handleToggleOnClick = useCallback(() => {
    setToggleOn(!toggleOn);
  }, [toggleOn]);

  function sendUpdate() {
    configFile.flags[flagId].state = enableDisable ? "ENABLED" : "DISABLED";
    configFile.flags[flagId].defaultVariant = toggleOn ? "on" : "off"; // TODO adopt this
    fetch("/api/write-to-file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: configFile }),
    })
      .then((response) => response.json())
      .then((data) => console.log(data))
      .then(() => setreloadData(true))
      .catch((error) => console.error(error));
    return;
  }
  const DynamicField = ({ flagConfig, flagId, setreloadData }) => {
    // Object.values(flagConfig.variants).every(value => typeof value === 'boolean')
    switch (JSON.stringify(flagConfig.variants)) {
      case JSON.stringify(enableDisableMapping):
        return (
          <div className="right-center-toggle-box">
            <button className="toggle-button" onClick={handleToggleOnClick}>
              {toggleOn ? "ON" : "OFF"}
            </button>
          </div>
        );
      default:
        return <div />;
    }
  };
  return (
    <div className="feature-flag">
      <div className="name-div">
        <div className="top-right-name">{flagId}</div>
        <input
          type="checkbox"
          className="enable-disable-checkbox"
          id="my-checkbox"
          checked={enableDisable}
          onChange={handleEnableDisableChange}
        />
        <label htmlFor="my-checkbox">Enable/Disable</label>
      </div>
      <DynamicField
        flagId={flagId}
        key={flagId}
        setreloadData={setreloadData}
        flagConfig={flagConfig}
      />
      <button className="send-button" onClick={sendUpdate}>
        Send
      </button>
    </div>
  );
}

export default FeatureFlag;