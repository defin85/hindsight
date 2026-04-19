"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle } from "lucide-react";
import { BankSelector } from "@/components/bank-selector";
import { useBank } from "@/lib/bank-context";
import { bankRoute } from "@/lib/bank-url";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export default function DashboardPage() {
  const router = useRouter();
  const { currentBank, banksError } = useBank();

  // Redirect to bank page if a bank is selected
  useEffect(() => {
    if (currentBank) {
      router.push(bankRoute(currentBank, "?view=data"));
    }
  }, [currentBank, router]);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <BankSelector />

      <div className="flex items-center justify-center h-[calc(100vh-80px)] bg-muted/20">
        <div className="w-full max-w-2xl px-6 space-y-4">
          {banksError && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Unable to load memory banks</AlertTitle>
              <AlertDescription>
                <p>{banksError.message}</p>
                {banksError.dataplane?.url && (
                  <p>
                    Dataplane URL: <code>{banksError.dataplane.url}</code>
                  </p>
                )}
                {banksError.dataplane?.error && <p>{banksError.dataplane.error}</p>}
                <p>
                  Check `HINDSIGHT_CP_DATAPLANE_API_URL` and that the API serves
                  `/v1/default/banks`.
                </p>
              </AlertDescription>
            </Alert>
          )}

          <div className="text-center p-10 bg-card rounded-lg border-2 border-border shadow-lg">
            <h3 className="text-2xl font-bold mb-3 text-card-foreground">Welcome to Hindsight</h3>
            <p className="text-muted-foreground mb-4">
              Select a memory bank from the dropdown above to get started.
            </p>
            <div className="text-6xl mb-4">🧠</div>
            <p className="text-sm text-muted-foreground">
              The sidebar will appear once you select a memory bank.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
