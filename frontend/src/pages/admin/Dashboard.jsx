import { useEffect, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useNavigate } from "react-router-dom";
import { ChartEmpty, MetricCard, NextStepCard, ShareStrip, directoryPath } from "../../components/AdminOps";
import {
  BarChartIcon,
  ClipboardListIcon,
  CreditCardIcon,
  FileTextIcon,
  MailIcon,
  PercentIcon,
  UsersIcon,
} from "../../components/icons";
import { Panel } from "../../components/RecordViews";
import { PortalShell } from "../../components/Layout";
import { LoadError } from "../../components/ui";
import { api } from "../../lib/api";
import { formatChartDate } from "../../lib/format";

function trendDate(bar) {
  const raw = bar?.payload?.date || bar?.date || "";
  const match = /^(\d{4}-\d{2}-\d{2})/.exec(String(raw));
  return match ? match[1] : "";
}

function DashboardSkeleton() {
  return (
    <div className="admin-dashboard" aria-hidden="true">
      <div className="metrics">
        {Array.from({ length: 4 }, (_, index) => <div className="card metric dash-skel" key={index} />)}
      </div>
      <div className="dash-actions">
        {Array.from({ length: 4 }, (_, index) => <div className="card dash-skel dash-skel-action" key={index} />)}
        <div className="card dash-skel dash-skel-action is-reports" />
      </div>
      <div className="grid-2">
        <div className="card dash-skel dash-skel-chart" />
        <div className="card dash-skel dash-skel-chart" />
      </div>
    </div>
  );
}

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  function load() {
    setError("");
    api("/api/admin/dashboard").then(setData).catch((err) => setError(err.message));
  }

  useEffect(() => {
    load();
  }, []);

  if (!data && !error) return <PortalShell role="Admin"><DashboardSkeleton /></PortalShell>;

  const dist = data?.alignment_distribution || {};
  const aligned = dist.Aligned || 0;
  const unknown = dist.Unknown || 0;
  const misaligned = dist.Misaligned || 0;
  const pending = data?.pending_approvals || 0;
  const pendingCards = data?.pending_card_applications || 0;
  const trend = data?.submission_trend || [];
  const angledLabels = trend.length > 8;

  return (
    <PortalShell role="Admin">
      {error ? (
        <LoadError onRetry={load}>{error}</LoadError>
      ) : null}
      {data && (
        <div className="admin-dashboard">
          <div className="metrics">
            <MetricCard
              emphasis
              label="Pending Approvals"
              value={data.pending_approvals}
              icon={<ClipboardListIcon size={18} />}
              hint="Alumni accounts whose status is Pending."
              to="/admin/approvals?from=dashboard"
              cta="Review queue →"
            />
            <MetricCard
              label="Total Tracer Submissions"
              value={data.total_submissions}
              icon={<FileTextIcon size={18} />}
              hint="All Graduate Tracer Survey submissions on file."
              to="/admin/records?from=dashboard"
              cta="View submissions →"
            />
            <MetricCard
              label="Approved Alumni"
              value={data.approved_alumni}
              icon={<UsersIcon size={18} />}
              hint="Alumni accounts whose status is Active."
              to={directoryPath("dashboard", { cohort: "status", status: "Active" })}
              cta="View alumni →"
            />
            <MetricCard
              label="Share Aligned"
              value={`${data.percent_aligned ?? 0}%`}
              icon={<PercentIcon size={18} />}
              hint="Aligned records divided by classified alignment records, to one decimal. This is not a share of all registered alumni."
              to={directoryPath("dashboard", { cohort: "alignment", alignment: "Aligned" })}
              cta="View aligned →"
            />
          </div>
          <section className="dash-band" aria-label="Quick actions">
            <h2 className="dash-band-title">Quick actions</h2>
            <div className="dash-actions">
              <NextStepCard
                title="Approval Queue"
                text="Open the registration review queue."
                value={`${pending} pending`}
                icon={<ClipboardListIcon size={18} />}
                to="/admin/approvals?from=dashboard"
                action="Review approvals"
              />
              <NextStepCard
                title="Alumni Cards"
                text="Alumni Card applications waiting for OAAPS review. Opens the Alumni Card page."
                value={`${pendingCards} for verification`}
                icon={<CreditCardIcon size={18} />}
                to="/admin/cards?from=dashboard"
                action="Open alumni cards"
              />
              <NextStepCard
                title="Tracer Records"
                text="Open the full submitted tracer records browser."
                icon={<FileTextIcon size={18} />}
                to="/admin/records?from=dashboard"
                action="Open records"
              />
              <NextStepCard
                title="Profile Updates"
                text="Open the profile-reminder management page."
                icon={<MailIcon size={18} />}
                to="/admin/profile-updates"
                action="Open requests"
              />
              <NextStepCard
                emphasis
                title="Reports"
                text="Open the detailed reporting area for institutional totals and OAAPS reports."
                icon={<BarChartIcon size={18} />}
                to="/admin/reports"
                action="View reports"
              />
            </div>
          </section>
          <div className="grid-2">
            <Panel title="Submission Trend" description="Tracer submissions grouped by the calendar date they were submitted.">
              {trend.length ? (
                <div className="chart-panel is-clickable">
                  <ResponsiveContainer width="100%" height={angledLabels ? 300 : 268}>
                    <BarChart
                      data={trend}
                      barCategoryGap="22%"
                      margin={{ top: 12, right: 8, left: 0, bottom: angledLabels ? 28 : 4 }}
                    >
                      <XAxis
                        dataKey="date"
                        tickFormatter={formatChartDate}
                        interval={0}
                        angle={angledLabels ? -32 : 0}
                        textAnchor={angledLabels ? "end" : "middle"}
                        height={angledLabels ? 52 : 32}
                        tick={{ fontSize: 12, fill: "#5b6777" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        allowDecimals={false}
                        domain={[0, (max) => Math.max(Number(max) || 0, 1)]}
                        width={32}
                        tick={{ fontSize: 12, fill: "#5b6777" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        formatter={(value) => {
                          const count = Number(value) || 0;
                          return [`${count} submission${count === 1 ? "" : "s"}`, "Submissions"];
                        }}
                        labelFormatter={(label) => formatChartDate(label) || label}
                        cursor={{ fill: "rgba(11,46,89,0.06)" }}
                        allowEscapeViewBox={{ x: true, y: true }}
                        wrapperStyle={{ zIndex: 4 }}
                      />
                      <Bar
                        dataKey="count"
                        fill="#0B2E59"
                        radius={[4, 4, 0, 0]}
                        maxBarSize={36}
                        cursor="pointer"
                        onClick={(bar) => {
                          const date = trendDate(bar);
                          if (date) navigate(`/admin/records?submitted_on=${encodeURIComponent(date)}&from=dashboard`);
                        }}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <ChartEmpty />
              )}
            </Panel>
            <Panel
              title="Employment Alignment"
              description="Counts and whole-percent shares of classified alignment records. Alumni without a classification are not included."
            >
              <ShareStrip
                emptyTitle="No alignment data yet"
                emptyText="Alignment counts will appear after tracer records are classified."
                items={[
                  { label: "Aligned", count: aligned, tone: "aligned", to: directoryPath("dashboard", { cohort: "alignment", alignment: "Aligned" }) },
                  { label: "Unknown", count: unknown, tone: "unknown", to: directoryPath("dashboard", { cohort: "alignment", alignment: "Unknown" }) },
                  { label: "Misaligned", count: misaligned, tone: "misaligned", to: directoryPath("dashboard", { cohort: "alignment", alignment: "Misaligned" }) },
                ]}
              />
            </Panel>
          </div>
        </div>
      )}
    </PortalShell>
  );
}
