import { useNavigate, useParams } from "react-router-dom";
import {
  ApprovalReviewContent,
  ApproveConfirmDialog,
  DecisionActions,
  DetailHeader,
  RejectConfirmDialog,
  isPendingRegistration,
  useApprovalReview,
} from "../../components/AdminReview";
import { PortalShell } from "../../components/Layout";
import { Alert, LoadError, PageSkeleton } from "../../components/ui";

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

  const pending = isPendingRegistration(review.detail);

  return (
    <PortalShell role="Admin">
      <div className="review-detail-shell">
        <DetailHeader
          backTo="/admin/approvals"
          backLabel="Back to Approval Queue"
          title="Registration Review"
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
          <ApprovalReviewContent
            key={review.detail.account.id}
            detail={review.detail}
            verify={review.verify}
            labels={review.labels}
            reviewTab={review.reviewTab}
            setReviewTab={review.setReviewTab}
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
        <ApproveConfirmDialog
          busy={review.busy}
          onConfirm={handleApprove}
          onClose={() => review.setConfirmApprove(false)}
        />
      ) : null}

      {review.confirmReject && review.detail ? (
        <RejectConfirmDialog
          reason={review.reason}
          setReason={review.setReason}
          reasonError={review.reasonError}
          setReasonError={review.setReasonError}
          busy={review.busy}
          onConfirm={handleReject}
          onClose={() => review.setConfirmReject(false)}
        />
      ) : null}
    </PortalShell>
  );
}
