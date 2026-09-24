import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  featuredAlumniPerk,
  parsePerkOffer,
  perkCategoryKey,
  perkLimitedHint,
  perkWebsiteLabel,
} from "./perkDisplay.js";

describe("perk display helpers", () => {
  it("parses percent, peso, and freeform offers", () => {
    assert.deepEqual(parsePerkOffer("15% off"), { kind: "percent", value: "15%", suffix: "OFF", raw: "15% off" });
    assert.equal(parsePerkOffer("Buy 1 Get 1").kind, "text");
    assert.equal(parsePerkOffer("₱500 off").kind, "amount");
    assert.equal(parsePerkOffer("₱500 off").value, "₱500");
    assert.equal(parsePerkOffer("Library access").suffix, "");
    assert.equal(parsePerkOffer("").value, "Perk");
  });

  it("shortens website URLs for listing cards", () => {
    assert.equal(perkWebsiteLabel("https://thecoffeeproject.com/"), "thecoffeeproject.com");
    assert.equal(perkWebsiteLabel("https://www.mesa.ph/menu"), "mesa.ph/menu");
    assert.equal(perkWebsiteLabel(""), "");
  });

  it("only labels limited-time offers from real validity dates", () => {
    const today = new Date(2026, 8, 22);
    assert.equal(perkLimitedHint({ status: "Available", valid_to: "2026-09-22" }, today), "Today only");
    assert.equal(perkLimitedHint({ status: "Available", valid_to: "2026-09-30" }, today), "Valid until Sep 30");
    assert.equal(perkLimitedHint({ status: "Available", valid_to: "2026-12-31" }, today), "");
    assert.equal(perkLimitedHint({ status: "Expired", valid_to: "2026-09-22" }, today), "");
  });

  it("features the soonest available limited-time perk", () => {
    const today = new Date(2026, 8, 22);
    const featured = featuredAlumniPerk(
      [
        { id: 1, status: "Available", valid_to: "2026-12-31", discount: "15% off" },
        { id: 2, status: "Available", valid_to: "2026-09-30", discount: "₱500 off" },
        { id: 3, status: "Expired", valid_to: "2026-09-23", discount: "20% off" },
      ],
      today
    );
    assert.equal(featured.id, 2);
    assert.equal(featuredAlumniPerk([{ id: 1, status: "Available", valid_to: "2026-12-31" }], today), null);
  });

  it("maps categories without hardcoding partner names", () => {
    assert.equal(perkCategoryKey("Coffee Shop"), "coffee");
    assert.equal(perkCategoryKey("Dining"), "dining");
    assert.equal(perkCategoryKey("Campus"), "campus");
    assert.equal(perkCategoryKey(""), "gift");
  });
});
