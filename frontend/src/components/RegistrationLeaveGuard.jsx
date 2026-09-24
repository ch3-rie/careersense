import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Dialog } from "./ui";

export default function RegistrationLeaveGuard({ armed }) {
  const navigate = useNavigate();
  const [pending, setPending] = useState(null);
  const bypassRef = useRef(false);
  const pendingRef = useRef(null);
  pendingRef.current = pending;

  useEffect(() => {
    if (!armed) return undefined;
    function onBeforeUnload(event) {
      if (bypassRef.current) return;
      event.preventDefault();
      event.returnValue = "";
    }
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [armed]);

  useEffect(() => {
    if (!armed) return undefined;
    if (!window.history.state?.csRegisterGuard) {
      window.history.pushState({ ...(window.history.state || {}), csRegisterGuard: true }, "");
    }
    function onPop(event) {
      if (bypassRef.current) return;
      event.stopImmediatePropagation();
      window.history.pushState({ ...(window.history.state || {}), csRegisterGuard: true }, "");
      setPending("back");
    }
    window.addEventListener("popstate", onPop, true);
    return () => window.removeEventListener("popstate", onPop, true);
  }, [armed]);

  useEffect(() => {
    if (!armed) return undefined;
    function onClick(event) {
      if (bypassRef.current || pendingRef.current) return;
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = event.target.closest?.("a[href]");
      if (!link || link.target === "_blank" || link.hasAttribute("download")) return;
      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin) return;
      const next = `${url.pathname}${url.search}${url.hash}`;
      const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      if (!next || next === current) return;
      event.preventDefault();
      event.stopPropagation();
      setPending(next);
    }
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [armed]);

  function stay() {
    setPending(null);
  }

  function leave() {
    const destination = pending;
    bypassRef.current = true;
    setPending(null);
    if (destination === "back") {
      window.history.go(-2);
      return;
    }
    navigate(destination || "/");
  }

  if (!pending) return null;
  return (
    <Dialog
      title="Cancel registration?"
      description="Your registration progress may be lost if you leave this page. Are you sure you want to cancel your registration?"
      hideActions
      onClose={stay}
      footer={(
        <>
          <button type="button" className="btn btn-danger" onClick={leave}>Cancel registration</button>
          <button type="button" className="btn btn-navy" onClick={stay}>Continue registration</button>
        </>
      )}
    />
  );
}
