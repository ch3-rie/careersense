import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Spinner } from "./components/ui";
import { useAuth } from "./lib/auth";
import AdminAccount from "./pages/admin/Account";
import AdminApprovalReview from "./pages/admin/ApprovalReview";
import AdminApprovals from "./pages/admin/Approvals";
import AdminDashboard from "./pages/admin/Dashboard";
import AdminRecordDetail from "./pages/admin/RecordDetail";
import AdminRecords from "./pages/admin/Records";
import AdminRegistry from "./pages/admin/Registry";
import AdminReports from "./pages/admin/Reports";
import AdminSoc from "./pages/admin/Soc";
import AdminSurvey from "./pages/admin/Survey";
import {
  AdminSurveyQuestionDetail,
  AdminSurveySectionDetail,
  AdminSurveyVersionDetail,
} from "./pages/admin/SurveyDetail";
import AdminPerks from "./pages/admin/Perks";
import AdminCards from "./pages/admin/Cards";
import AdminProfileUpdates from "./pages/admin/ProfileUpdates";
import AdminUsers from "./pages/admin/Users";
import AlumniAccount from "./pages/alumni/Account";
import AlumniCardPage from "./pages/alumni/Card";
import AlumniDashboard from "./pages/alumni/Dashboard";
import AlumniPerksPage from "./pages/alumni/Perks";
import AlumniResume from "./pages/alumni/Resume";
import LandingPage from "./pages/public/Landing";
import LoginPage from "./pages/public/Login";
import ForgotPasswordPage, { ResetPasswordPage, VerifyResetPinPage } from "./pages/public/ForgotPassword";
import PendingPage from "./pages/public/Pending";
import RegisterPage from "./pages/public/Register";
import RejectedPage from "./pages/public/Rejected";
import { justRegistered } from "./lib/registerSession";

function homeFor(user) {
  if (!user) return "/login";
  if (user.role === "Admin") return "/admin";
  if (user.status === "Pending") return "/pending";
  if (user.status === "Rejected") return "/rejected";
  return "/alumni";
}

function Guard({ role, allowStatus, children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) return <Navigate to={homeFor(user)} replace />;
  if (allowStatus && user.role !== "Admin" && !allowStatus.includes(user.status)) {
    return <Navigate to={homeFor(user)} replace />;
  }
  if (user.role === "Admin" && user.must_change_password && location.pathname !== "/admin/account") {
    return <Navigate to="/admin/account" replace />;
  }
  return children;
}

function PublicOnly({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (user) return <Navigate to={homeFor(user)} replace />;
  return children;
}

function RegisterGate({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (user?.role === "Admin") return <Navigate to="/admin" replace />;
  if (user?.role === "Alumni" && user.status === "Active") return <Navigate to="/alumni" replace />;
  if (user?.role === "Alumni" && user.status === "Rejected") return <Navigate to="/rejected" replace />;
  if (user?.role === "Alumni" && user.status === "Pending" && !justRegistered()) {
    return <Navigate to="/pending" replace />;
  }
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<PublicOnly><LoginPage /></PublicOnly>} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/forgot-password/verify" element={<VerifyResetPinPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/register" element={<RegisterGate><RegisterPage /></RegisterGate>} />
      <Route path="/pending" element={<Guard role="Alumni" allowStatus={["Pending"]}><PendingPage /></Guard>} />
      <Route path="/rejected" element={<Guard role="Alumni" allowStatus={["Rejected"]}><RejectedPage /></Guard>} />

      <Route path="/alumni" element={<Guard role="Alumni" allowStatus={["Active"]}><AlumniDashboard /></Guard>} />
      <Route path="/alumni/card" element={<Guard role="Alumni" allowStatus={["Active"]}><AlumniCardPage /></Guard>} />
      <Route path="/alumni/perks" element={<Guard role="Alumni" allowStatus={["Active"]}><AlumniPerksPage /></Guard>} />
      <Route path="/alumni/resume" element={<Guard role="Alumni" allowStatus={["Active"]}><AlumniResume /></Guard>} />
      <Route path="/alumni/account" element={<Guard role="Alumni" allowStatus={["Active"]}><AlumniAccount /></Guard>} />
      <Route path="/alumni/profile" element={<Navigate to="/alumni" replace />} />

      <Route path="/admin" element={<Guard role="Admin"><AdminDashboard /></Guard>} />
      <Route path="/admin/approvals" element={<Guard role="Admin"><AdminApprovals /></Guard>} />
      <Route path="/admin/approvals/:id" element={<Guard role="Admin"><AdminApprovalReview /></Guard>} />
      <Route path="/admin/records" element={<Guard role="Admin"><AdminRecords /></Guard>} />
      <Route path="/admin/records/:id" element={<Guard role="Admin"><AdminRecordDetail /></Guard>} />
      <Route path="/admin/profile-updates" element={<Guard role="Admin"><AdminProfileUpdates /></Guard>} />
      <Route path="/admin/survey" element={<Guard role="Admin"><AdminSurvey /></Guard>} />
      <Route path="/admin/survey/questions/:questionId" element={<Guard role="Admin"><AdminSurveyQuestionDetail /></Guard>} />
      <Route path="/admin/survey/sections/:sectionId" element={<Guard role="Admin"><AdminSurveySectionDetail /></Guard>} />
      <Route path="/admin/survey/versions/:versionNumber" element={<Guard role="Admin"><AdminSurveyVersionDetail /></Guard>} />
      <Route path="/admin/perks" element={<Guard role="Admin"><AdminPerks /></Guard>} />
      <Route path="/admin/cards" element={<Guard role="Admin"><AdminCards /></Guard>} />
      <Route path="/admin/soc" element={<Guard role="Admin"><AdminSoc /></Guard>} />
      <Route path="/admin/registry" element={<Guard role="Admin"><AdminRegistry /></Guard>} />
      <Route path="/admin/reports" element={<Guard role="Admin"><AdminReports /></Guard>} />
      <Route path="/admin/users" element={<Guard role="Admin"><AdminUsers /></Guard>} />
      <Route path="/admin/account" element={<Guard role="Admin"><AdminAccount /></Guard>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
