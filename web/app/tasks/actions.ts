"use server";

import { revalidatePath } from "next/cache";
import { ApiError, advanceTaskStatus } from "@/lib/api";
import { getSessionToken } from "@/lib/session";

/**
 * Server action for the tasks table. Advancing a task (open -> in_progress -> done) runs
 * SERVER-SIDE so the per-user Supabase bearer (httpOnly cookie) authorizes it — the backend
 * gates status changes to team roles, so a client-role session will get a 403 here.
 */

export interface TaskActionResult {
  ok: boolean;
  error?: string;
}

export async function advanceTaskAction(
  taskId: string,
  status: string,
): Promise<TaskActionResult> {
  const token = await getSessionToken();
  if (token === null) {
    return { ok: false, error: "Your session has expired — sign in again." };
  }
  try {
    await advanceTaskStatus(taskId, status, token);
    revalidatePath("/tasks");
    return { ok: true };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 403) {
        return { ok: false, error: "You don't have permission to change task status." };
      }
      if (error.status === 404) {
        return { ok: false, error: "This task no longer exists." };
      }
    }
    return { ok: false, error: "Could not update the task. Try again." };
  }
}
