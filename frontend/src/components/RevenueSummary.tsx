import React, { useEffect, useState } from "react";
import { SecureAPI } from "../lib/secureApi";

interface RevenueData {
  property_id: string;
  total_revenue: number;
  currency: string;
  reservations_count: number;
}

export interface ReportingPeriod {
  month: number; // 1-12
  year: number;
}

interface RevenueSummaryProps {
  propertyId: string;
  period?: ReportingPeriod | null;
  showRaw?: boolean;
}

const periodLabel = (period?: ReportingPeriod | null): string => {
  if (!period) return "All time";
  return new Date(period.year, period.month - 1, 1).toLocaleString(undefined, {
    month: "long",
    year: "numeric",
  });
};

export const RevenueSummary: React.FC<RevenueSummaryProps> = ({
  propertyId,
  period,
  showRaw,
}) => {
  const [data, setData] = useState<RevenueData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const month = period?.month;
  const year = period?.year;

  useEffect(() => {
    // If the user switches property or month while a request is in flight,
    // ignore the older response so it can't overwrite the newer one.
    let cancelled = false;

    const fetchRevenue = async () => {
      setLoading(true);
      setError("");
      setData(null);
      try {
        // FIX: no more simulated tenant header. The backend decides the
        // client from the auth token alone.
        const response = await SecureAPI.getDashboardSummary(
          propertyId,
          month && year ? { month, year } : undefined,
        );
        if (!cancelled) setData(response);
      } catch (err) {
        if (!cancelled) {
          setError("Failed to load revenue data");
          console.error(err);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchRevenue();
    return () => {
      cancelled = true;
    };
  }, [propertyId, month, year]);

  if (loading) {
    return (
      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-100 rounded w-1/4"></div>
          <div className="h-8 bg-gray-100 rounded w-1/2"></div>
          <div className="flex gap-4 pt-4">
            <div className="h-12 bg-gray-100 rounded flex-1"></div>
            <div className="h-12 bg-gray-100 rounded flex-1"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error)
    return <div className="p-4 text-red-500 bg-red-50 rounded-lg">{error}</div>;
  if (!data) return null;

  // FIX: the backend already rounds to cents with Decimal, so the card only
  // formats the value. It used to re-round with Math.round(total * 100) / 100,
  // and float math turns 1.005 * 100 into 100.49999999999999, losing a cent.
  const formattedTotal = data.total_revenue.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow duration-300">
      {showRaw && (
        <div className="p-3 bg-gray-50 text-xs font-mono border-b border-gray-100 overflow-auto max-h-32">
          <strong className="block mb-1 text-gray-500 uppercase tracking-wider text-[10px]">
            Raw API Response
          </strong>
          <pre className="text-gray-700">{JSON.stringify(data, null, 2)}</pre>
        </div>
      )}

      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide">
              Total Revenue · {periodLabel(period)}
            </h2>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-3xl font-bold text-gray-900 tracking-tight">
                {data.currency} {formattedTotal}
              </span>
              {/* Removed: a hardcoded "+12%" trend badge that wasn't calculated from any data. */}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-100">
          <div>
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">
              Property ID
            </p>
            <p className="text-sm font-semibold text-gray-700 font-mono mt-1">
              {data.property_id}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">
              Reservations
            </p>
            <p className="text-sm font-semibold text-gray-700 mt-1">
              {data.reservations_count}{" "}
              <span className="font-normal text-gray-400">bookings</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
