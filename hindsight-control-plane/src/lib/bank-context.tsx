"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import { client, type DataplaneHealthStatus } from "./api";

interface BankLoadError {
  message: string;
  dataplane?: DataplaneHealthStatus;
}

interface BankContextType {
  currentBank: string | null;
  setCurrentBank: (bank: string | null) => void;
  banks: string[];
  banksError: BankLoadError | null;
  loadBanks: () => Promise<void>;
}

const BankContext = createContext<BankContextType | undefined>(undefined);

export function BankProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [currentBank, setCurrentBank] = useState<string | null>(null);
  const [banks, setBanks] = useState<string[]>([]);
  const [banksError, setBanksError] = useState<BankLoadError | null>(null);

  const loadBanks = async () => {
    try {
      const response = await client.listBanks();
      // Extract bank_id from each bank object
      const bankIds = response.banks?.map((bank: any) => bank.bank_id) || [];
      setBanks(bankIds);
      setBanksError(null);
    } catch (error) {
      console.error("Error loading banks:", error);
      setBanks([]);

      // When the bank list fails, fetch control-plane health so the UI can show
      // the configured dataplane URL. Without this, a wrong port looks identical
      // to an empty bank list and users end up debugging the wrong layer.
      let dataplane: DataplaneHealthStatus | undefined;
      try {
        const health = await client.getHealth();
        dataplane = health.dataplane;
      } catch (healthError) {
        console.error("Error loading control-plane health:", healthError);
      }

      setBanksError({
        message: error instanceof Error ? error.message : "Failed to load memory banks",
        dataplane,
      });
    }
  };

  // Initialize bank from URL on mount
  useEffect(() => {
    const bankMatch = pathname?.match(/^\/banks\/([^/?]+)/);
    if (bankMatch) {
      setCurrentBank(decodeURIComponent(bankMatch[1]));
    }
  }, [pathname]);

  useEffect(() => {
    loadBanks();
  }, []);

  return (
    <BankContext.Provider value={{ currentBank, setCurrentBank, banks, banksError, loadBanks }}>
      {children}
    </BankContext.Provider>
  );
}

export function useBank() {
  const context = useContext(BankContext);
  if (context === undefined) {
    throw new Error("useBank must be used within a BankProvider");
  }
  return context;
}
