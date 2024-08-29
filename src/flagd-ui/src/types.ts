interface FlagConfig {
  description: string;
  state: "ENABLED" | "DISABLED";
  variants: {};
  defaultVariant: "on" | "off";
}

type Flags = {
  [key: string]: FlagConfig;
};

interface ConfigFile {
  $schema: string;
  flags: Flags;
}
