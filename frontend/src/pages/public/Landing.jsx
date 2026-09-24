import { Link } from "react-router-dom";
import { PublicFooter, PublicHeader } from "../../components/Layout";

const FEATURES = [
  ["01", "Resume capture", "Alumni upload a PDF or DOCX instead of retyping a long survey from scratch."],
  ["02", "AI extraction", "Education, work history, skills, and job titles are read from the resume and mapped to Graduate Tracer Survey fields."],
  ["03", "Review before submit", "Graduates check and correct every field before the Alumni Office receives the record."],
  ["04", "SOC mapping", "Job titles are classified against PSOC/SOC codes used in career alignment."],
  ["05", "Analytics", "Alignment status, employment trends, and tracer history are available to alumni and administrators."],
  ["06", "Secure access", "Role-based portals keep pending, active, and rejected alumni on the correct path."],
];

export default function LandingPage() {
  return (
    <>
      <PublicHeader />
      <main id="main">
        <section className="hero">
          <div className="container hero-grid">
            <div>
              <span className="kicker">Office of Alumni Affairs and Placement Services</span>
              <h1>Know where AUF graduates build their careers.</h1>
              <p>
                CareerSense is the Graduate Tracer System of Angeles University Foundation.
                Upload a resume, review the extracted tracer information, and help the University
                understand employment outcomes without repeating a long paper survey.
              </p>
              <div className="hero-actions">
                <Link className="btn btn-primary" to="/register">Upload resume</Link>
                <Link className="btn btn-ghost" to="/login">Sign in</Link>
              </div>
            </div>
            <div className="hero-card">
              <strong>How a tracer record is created</strong>
              <ol>
                <li>Upload your resume to start a temporary draft.</li>
                <li>Review and submit the Graduate Tracer Survey.</li>
                <li>OAAPS verifies your graduate record.</li>
                <li>Approved alumni can access the portal and update their career information.</li>
              </ol>
            </div>
          </div>
        </section>

        <section className="section" id="features">
          <div className="container">
            <h2>Built for institutional tracer work</h2>
            <p className="lead">The same CHED-aligned instrument, with less manual encoding for alumni and staff.</p>
            <div className="grid-3">
              {FEATURES.map(([num, title, text]) => (
                <article className="card" key={num}>
                  <div className="feature-icon">{num}</div>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="section alt" id="how">
          <div className="container">
            <h2>From resume to institutional insight</h2>
            <p className="lead">Four steps from registration to OAAPS reporting.</p>
            <div className="grid-4">
              {[
                ["Register", "Match your email to AUF graduate records and consent to data processing."],
                ["Upload", "The system extracts education, employment, and skills from your resume."],
                ["Validate", "You correct the Graduate Tracer Survey before it is stored."],
                ["Insights", "Alignment status, PSOC classification, and reports become available to OAAPS."],
              ].map(([title, text], i) => (
                <article className="card" key={title}>
                  <div className="badge">Step {i + 1}</div>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
