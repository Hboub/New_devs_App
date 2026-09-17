import React, { useEffect, useState } from "react";
import { RevenueSummary, ReportingPeriod } from "./RevenueSummary";
import { SecureAPI } from "../lib/secureApi";

interface Property {
  id: string;
  name: string;
  timezone: string;
}

// The last 36 months, newest first, as { value: "YYYY-MM", label: "March 2024" }.
const buildMonthOptions = (count: number) => {
  const now = new Date();
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    return {
      value: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`,
      label: d.toLocaleString(undefined, { month: "long", year: "numeric" }),
    };
  });
};

const MONTH_OPTIONS = buildMonthOptions(36);

const Dashboard: React.FC = () => {
  // FIX: this used to be a hardcoded list of all five properties, shared by every
  // client, so Ocean could pick (and see names of) Sunset's properties.
  const [properties, setProperties] = useState<Property[]>([]);
  const [loadingProperties, setLoadingProperties] = useState(true);
  const [propertiesError, setPropertiesError] = useState("");
  const [selectedProperty, setSelectedProperty] = useState("");
  const [selectedMonth, setSelectedMonth] = useState(""); // "" means all time

  useEffect(() => {
    let cancelled = false;

    SecureAPI.getDashboardProperties()
      .then((list) => {
        if (cancelled) return;
        setProperties(list);
        setSelectedProperty(list[0]?.id ?? "");
      })
      .catch((err) => {
        if (cancelled) return;
        console.error(err);
        setPropertiesError("Failed to load properties");
      })
      .finally(() => {
        if (!cancelled) setLoadingProperties(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const period: ReportingPeriod | null = selectedMonth
    ? {
        year: Number(selectedMonth.slice(0, 4)),
        month: Number(selectedMonth.slice(5, 7)),
      }
    : null;

  const selectClass =
    "block w-full sm:w-auto min-w-[200px] px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm";

  return (
    <div className="p-4 lg:p-6 min-h-full">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-2xl font-bold mb-6 text-gray-900">
          Property Management Dashboard
        </h1>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 lg:p-6">
          <div className="mb-6">
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4">
              <div>
                <h2 className="text-lg lg:text-xl font-medium text-gray-900 mb-2">
                  Revenue Overview
                </h2>
                <p className="text-sm lg:text-base text-gray-600">
                  Monthly performance insights for your properties
                </p>
              </div>

              <div className="flex flex-col sm:flex-row gap-4">
                {/* Property Selector */}
                <div className="flex flex-col sm:items-end">
                  <label
                    htmlFor="property-select"
                    className="text-xs font-medium text-gray-700 mb-1"
                  >
                    Select Property
                  </label>
                  <select
                    id="property-select"
                    value={selectedProperty}
                    onChange={(e) => setSelectedProperty(e.target.value)}
                    disabled={loadingProperties || properties.length === 0}
                    className={selectClass}
                  >
                    {properties.map((property) => (
                      <option key={property.id} value={property.id}>
                        {property.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Period Selector: months are counted in each property's local time */}
                <div className="flex flex-col sm:items-end">
                  <label
                    htmlFor="period-select"
                    className="text-xs font-medium text-gray-700 mb-1"
                  >
                    Period
                  </label>
                  <select
                    id="period-select"
                    value={selectedMonth}
                    onChange={(e) => setSelectedMonth(e.target.value)}
                    className={selectClass}
                  >
                    <option value="">All time</option>
                    {MONTH_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            {loadingProperties && (
              <p className="text-sm text-gray-500">Loading properties…</p>
            )}
            {propertiesError && (
              <div className="p-4 text-red-500 bg-red-50 rounded-lg">
                {propertiesError}
              </div>
            )}
            {!loadingProperties &&
              !propertiesError &&
              properties.length === 0 && (
                <p className="text-sm text-gray-500">
                  No properties found for your account.
                </p>
              )}
            {selectedProperty && (
              <RevenueSummary propertyId={selectedProperty} period={period} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
