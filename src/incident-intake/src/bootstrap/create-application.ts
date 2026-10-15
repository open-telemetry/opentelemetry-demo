import { ProcessAlertNotificationUseCase } from "../application/use-cases.js";
import type { IntakeDependencies } from "../application/use-cases.js";

export function createApplication(dependencies: IntakeDependencies) {
  return { processAlertNotification: new ProcessAlertNotificationUseCase(dependencies) };
}
