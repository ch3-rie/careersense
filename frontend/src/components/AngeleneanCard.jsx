import { fullName } from "../lib/format";

function initials(profile) {
  const first = String(profile?.first_name || "").trim();
  const last = String(profile?.last_name || "").trim();
  return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase() || "A";
}

const CODE128 = [
  "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
  "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
  "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
  "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
  "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
  "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
  "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
  "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
  "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
  "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
  "114131", "311141", "411131", "211412", "211214", "211232", "2331112",
];

function code128Modules(value) {
  const text = String(value || "").trim();
  if (!text || [...text].some((char) => char.charCodeAt(0) < 32 || char.charCodeAt(0) > 126)) return [];
  const values = [...text].map((char) => char.charCodeAt(0) - 32);
  let checksum = 104;
  values.forEach((symbol, index) => {
    checksum += symbol * (index + 1);
  });
  checksum %= 103;
  const symbols = [104, ...values, checksum, 106];
  const modules = [];
  symbols.forEach((symbol) => {
    const pattern = CODE128[symbol];
    let bar = true;
    [...pattern].forEach((digit) => {
      modules.push({ bar, width: Number(digit) });
      bar = !bar;
    });
  });
  return modules;
}

export function cardBarcodeValue(identity, card) {
  const cardNumber = String(card?.card_number || "").trim();
  const studentId = String(identity?.student_number || identity?.student_id || "").trim();
  return cardNumber || studentId;
}

function CardBarcode({ value }) {
  const modules = code128Modules(value);
  if (!modules.length) return null;
  const quiet = 10;
  const width = modules.reduce((sum, module) => sum + module.width, 0) + quiet * 2;
  let cursor = quiet;
  const bars = modules.map((module, index) => {
    const x = cursor;
    cursor += module.width;
    if (!module.bar) return null;
    return <rect key={index} x={x} y="0" width={module.width} height="42" />;
  });
  return (
    <figure className="angelenean-barcode">
      <svg viewBox={`0 0 ${width} 42`} role="img" aria-label={`Barcode ${value}`}>
        {bars}
      </svg>
      <figcaption>{value}</figcaption>
    </figure>
  );
}

export function DigitalAlumniCard({ identity = {}, card = {}, photoSrc = "" }) {
  const name = fullName(identity);
  const studentId = identity.student_number || identity.student_id || "";
  const degree = identity.degree || "";
  const batch = identity.year_graduated ? String(identity.year_graduated) : "";
  const barcode = cardBarcodeValue(identity, card);
  const photoLabel = name && name !== "—" ? `${name} profile photo` : "Profile photo";

  return (
    <article className="angelenean-card" aria-label="Angelenean Alumni Card">
      <header className="angelenean-card-head">
        <img src="/assets/AUF-logo.png" alt="" />
        <div>
          <p>Angeles University Foundation</p>
          <h2>ANGELENEAN ALUMNI CARD</h2>
        </div>
      </header>
      <div className="angelenean-card-main">
        <dl>
          <div>
            <dt>Name</dt>
            <dd>{name}</dd>
          </div>
          <div>
            <dt>Alumni ID</dt>
            <dd>{studentId || "—"}</dd>
          </div>
          <div>
            <dt>Degree</dt>
            <dd>{degree || "—"}</dd>
          </div>
          <div>
            <dt>Batch</dt>
            <dd>{batch || "—"}</dd>
          </div>
        </dl>
        <div className="angelenean-card-side">
          <div className="angelenean-card-photo">
            {photoSrc ? (
              <img src={photoSrc} alt={photoLabel} />
            ) : (
              <span aria-hidden="true">{initials(identity)}</span>
            )}
          </div>
          {barcode ? <CardBarcode value={barcode} /> : null}
        </div>
      </div>
    </article>
  );
}
