export class NotImplementedError extends Error {
  constructor(component: string) {
    super(`${component} is an architectural scaffold; behavior is not implemented.`);
    this.name = "NotImplementedError";
  }
}
