import { useEffect, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartEmpty, MetricCard, NextStepCard, ShareStrip } from "../../components/AdminOps";
import {
  ClipboardListIcon,
  FileTextIcon,
  PercentIcon,
  UsersIcon,
} from "../../components/icons";
import { Panel } from "../../components/RecordViews";
import { PortalShell } from "../../components/Layout";
import { LoadError, PageSkeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { formatChartDate } from "../../lib/format";

export default function AdminDashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  function load() {
    setError("");
    api("/api/admin/dashboard").then(setData).catch((err) => setError(err.message));
  }

  useEffect(() => {
    load();
  }, []);

  if (!data && !error) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  const dist = data?.alignment_distribution || {};
  const aligned = dist.Aligned || 0;
  const unknown = dist.Unknown || 0;
  const misaligned = dist.Misaligned || 0;
  const pending = data?.pending_approvals || 0;
  const pendingCards = data?.pending_card_applications || 0;

  return (
    <PortalShell role="Admin">
      {error ? (
        <LoadError onRetry={load}>{error}</LoadError>
      ) : null}
      {data && (
        <>
          <div className="metrics">
            <MetricCard
              label="Pending Approvals"
              value={data.pending_approvals}
              icon={<ClipboardListIcon size={18} />}
              hint="Registrations waiting for review"
              to="/admin/approvals"
              cta="Review queue →"
            />
            <MetricCard
              label="Total Tracer Submissions"
              value={data.total_submissions}
              icon={<FileTextIcon size={18} />}
              hint="Submitted Graduate Tracer Survey records"
            />
            <MetricCard
              label="Approved Alumni"
              value={data.approved_alumni}
              icon={<UsersIcon size={18} />}
              hint="Active alumni accounts"
            />
            <MetricCard
              label="Share Aligned"
              value={`${data.percent_aligned ?? 0}%`}
              icon={<PercentIcon size={18} />}
              hint="Classified employment records marked Aligned"
            />
          </div>
          <div className="next-grid">
            <NextStepCard
              title="Approval Queue"
              text="Registrations waiting for verification"
              value={`${pending} pending`}
              to="/admin/approvals"
              action="Review approvals"
            />
            <NextStepCard
              title="Alumni Cards"
              text="AAC applications waiting for AAPS review"
              value={`${pendingCards} for verification`}
              to="/admin/cards"
              action="Review cards"
            />
            <NextStepCard
              title="Tracer Records"
              text="Search submitted Graduate Tracer Survey records"
              to="/admin/records"
              action="Open records"
            />
            <NextStepCard
              title="Profile Updates"
              text="Request updates or schedule automated profile reminder emails"
              to="/admin/profile-updates"
              action="Open requests"
            />
            <NextStepCard
              title="Reports"
              text="View institutional totals and generate OAAPS reports"
              to="/admin/reports"
              action="View reports"
            />
          </div>
          <div className="grid-2">
            <Panel title="Submission Trend">
              {data.submission_trend.length ? (
                <div className="chart-panel">
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={data.submission_trend} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                      <XAxis
                        dataKey="date"
                        tickFormatter={formatChartDate}
                        tick={{ fontSize: 14, fill: "#5b6777" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        allowDecimals={false}
                        tick={{ fontSize: 14, fill: "#5b6777" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        formatter={(value) => [`${value} submission${value === 1 ? "" : "s"}`, "Count"]}
                        labelFormatter={(label) => formatChartDate(label) || label}
                        cursor={{ fill: "rgba(11,46,89,0.06)" }}
                      />
                      <Bar dataKey="count" fill="#0B2E59" radius={[4, 4, 0, 0]} maxBarSize={42} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <ChartEmpty />
              )}
            </Panel>
            <Panel title="Employment Alignment">
              <ShareStrip
                emptyTitle="No alignment data yet"
                emptyText="Alignment counts will appear after tracer records are classified."
                items={[
                  { label: "Aligned", count: aligned, tone: "aligned" },
                  { label: "Unknown", count: unknown, tone: "unknown" },
                  { label: "Misaligned", count: misaligned, tone: "misaligned" },
                ]}
              />
            </Panel>
          </div>
        </>
      )}
    </PortalShell>
  );
}
