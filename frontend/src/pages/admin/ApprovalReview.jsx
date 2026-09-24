import { useNavigate, useParams } from "react-router-dom";
import {
  ApprovalDetailView,
  DecisionActions,
  DetailHeader,
  applicantName,
  isPendingRegistration,
  registrationStatusLabel,
  useApprovalReview,
  verifyShortLabel,
} from "../../components/AdminReview";
import { PortalShell } from "../../components/Layout";
import { Alert, Dialog, Field, LoadError, PageSkeleton } from "../../components/ui";

export default function AdminApprovalReview() {
  const { id } = useParams();
  const navigate = useNavigate();
  const accountId = Number(id);
  const review = useApprovalReview(Number.isFinite(accountId) ? accountId : null);

  async function handleApprove() {
    const ok = await review.approve();
    if (ok) {
      navigate("/admin/approvals", {
        state: {
          noticeTitle: "Registration approved successfully.",
          notice: "The alumni account is now active and verified.",
        },
      });
    }
  }

  async function handleReject() {
    const ok = await review.reject();
    if (ok) {
      navigate("/admin/approvals", {
        state: {
          noticeTitle: "Registration rejected successfully.",
          notice: "The applicant cannot access the alumni portal and will see this reason.",
        },
      });
    }
  }

  if (review.loading && !review.detail) {
    return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;
  }

  const name = applicantName(review.detail) || "Registration Review";
  const status = review.detail?.account?.status || "Pending";
  const pending = isPendingRegistration(review.detail);

  return (
    <PortalShell role="Admin">
      <div className="review-detail-shell">
        <DetailHeader
          backTo="/admin/approvals"
          backLabel="Back to Approval Queue"
          title="Registration Review"
          name={review.detail ? name : null}
          meta={review.detail ? `${registrationStatusLabel(status)} · ${verifyShortLabel(review.verify)}` : null}
          actions={
            review.detail && pending ? (
              <DecisionActions
                compact
                busy={review.busy}
                onApprove={review.requestApprove}
                onReject={review.requestReject}
              />
            ) : null
          }
        />
        <Alert type="error">{review.error}</Alert>
        <Alert type="ok" title={review.okTitle}>{review.ok}</Alert>
        {review.error && !review.detail ? (
          <LoadError onRetry={review.reload}>{review.error}</LoadError>
        ) : review.detail ? (
          <ApprovalDetailView
            detail={review.detail}
            verify={review.verify}
            labels={review.labels}
            reason={review.reason}
            setReason={review.setReason}
            reasonError={review.reasonError}
            setReasonError={review.setReasonError}
            busy={review.busy}
            onApprove={review.requestApprove}
            onReject={review.requestReject}
            onDownloadResume={review.downloadResume}
          />
        ) : null}
      </div>

      {review.confirmApprove && review.detail ? (
        <Dialog
          title="Approve this registration?"
          confirmLabel="Approve"
          busy={review.busy}
          onConfirm={handleApprove}
          onClose={() => review.setConfirmApprove(false)}
        >
          <p>
            Approving this registration will activate the alumni account and mark the graduate as verified.
            They will be able to access the Alumni Portal.
          </p>
        </Dialog>
      ) : null}

      {review.confirmReject && review.detail ? (
        <Dialog
          title="Reject this registration?"
          confirmLabel="Reject"
          danger
          busy={review.busy}
          onConfirm={handleReject}
          onClose={() => review.setConfirmReject(false)}
        >
          <p>The applicant will remain unable to access the alumni portal and will see this reason.</p>
          <Field label="Reason for Rejection" required error={review.reasonError}>
            <textarea
              id="rejection-reason-dialog"
              value={review.reason}
              onChange={(e) => {
                review.setReason(e.target.value);
                if (e.target.value.trim().length >= 3) review.setReasonError("");
              }}
              placeholder="Explain why this registration cannot be approved."
            />
          </Field>
        </Dialog>
      ) : null}
    </PortalShell>
  );
}
