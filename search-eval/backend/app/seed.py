"""Seed the platform with a fully synthetic local corpus (home coffee
brewing), queries, two judges, one versioned judgment set, and two
experiments. The corpus deliberately contains:

* a query with ZERO relevant documents (q06),
* two documents with identical text producing TIED scores (d30/d31),
* one document indexed TWICE under the same logical doc_id (d12),
  simulating re-ingestion duplicates that the pipeline must not
  double-count.

Run:  python -m app.seed
"""
from __future__ import annotations

from .db import Base, SessionLocal, engine
from . import models, retrieval, services

INDEX = "docs"

# (doc_id, title, text)
DOCS = [
    ("d01", "Pour Over Coffee: A Complete Guide",
     "Pour over brewing gives you control over water flow. Use a gooseneck "
     "kettle, medium-fine grounds, and pour in slow spirals for even extraction."),
    ("d02", "Bloom Your Coffee",
     "Blooming pours a small amount of hot water over grounds to release "
     "trapped gas before the main pour over brew begins."),
    ("d03", "Choosing a Gooseneck Kettle",
     "A gooseneck kettle gives precise pouring control for pour over methods "
     "like the V60 and Chemex brewers."),
    ("d04", "Best Coffee Scales",
     "A scale with a timer helps you hit the right coffee to water ratio "
     "for every brew, pour over or immersion."),
    ("d05", "Espresso Pressure Explained",
     "Nine bars of pressure is the classic espresso target. Modern machines "
     "let you profile pressure through the shot for different flavors."),
    ("d06", "Dialing In Espresso",
     "Adjust grind size, dose, and yield to balance sour and bitter flavors "
     "in your espresso shot. Change one variable at a time."),
    ("d07", "Espresso Machine Maintenance",
     "Backflush weekly and descale monthly to keep pump pressure stable and "
     "espresso tasting clean. Replace gaskets yearly."),
    ("d08", "Pre-Infusion Basics",
     "Gentle pre-infusion wets the puck at low pressure before full "
     "extraction, reducing channeling in espresso."),
    ("d09", "Cold Brew at Home",
     "Steep coarse grounds in cold water for 12 to 18 hours, then filter. "
     "Cold brew is smooth, sweet, and low in acidity."),
    ("d10", "Cold Brew Concentrate",
     "Use a 1 to 4 coffee to water ratio for concentrate; dilute with water "
     "or milk before serving. Steep 16 hours at room temperature."),
    ("d11", "Iced Coffee vs Cold Brew",
     "Iced coffee is hot-brewed coffee chilled over ice; cold brew is "
     "steeped cold for many hours and tastes smoother."),
    ("d12", "Water Temperature for Coffee",
     "The ideal brewing water temperature is 90 to 96 degrees Celsius. "
     "Water that is too hot scorches grounds; too cool under-extracts."),
    ("d13", "Kettle Temperature Control",
     "Variable temperature kettles hold water within a degree, which "
     "matters for delicate light roasts and for tea."),
    ("d14", "Why Boiling Water Ruins Coffee",
     "Water straight off the boil can over-extract bitter compounds. "
     "Let the kettle rest 30 seconds before brewing."),
    ("d15", "Burr vs Blade Grinders",
     "Burr grinders crush beans between two burrs for uniform particles; "
     "blade grinders chop unevenly, which hurts extraction consistency."),
    ("d16", "Grind Size Chart",
     "Extra coarse for cold brew, coarse for french press, medium for drip "
     "and pour over, fine for espresso."),
    ("d17", "Hand Grinders for Travel",
     "A compact hand grinder with steel burrs keeps your grind consistent "
     "away from home and doubles as a workout."),
    ("d18", "French Press Ratio Guide",
     "Start with a 1 to 15 coffee to water ratio for french press. Steep "
     "four minutes, break the crust, then plunge slowly."),
    ("d19", "French Press Grind",
     "Coarse, even grounds keep sludge out of your cup and prevent "
     "over-extraction during the four minute steep."),
    ("d20", "Cleaning a French Press",
     "Disassemble the mesh filter after each use; old coffee oils turn "
     "rancid and spoil the next brew."),
    ("d21", "Milk Frothing Temperature",
     "Steam milk to 55 to 65 degrees Celsius. Beyond 70 the proteins break "
     "down and the natural sweetness fades."),
    ("d22", "Latte Art for Beginners",
     "Silky microfoam matters more than pouring technique. Stretch the milk "
     "less than you think, then swirl to polish."),
    ("d23", "Non-Dairy Milks for Coffee",
     "Oat milk steams closest to dairy; almond milk separates at high "
     "temperature; soy foams well but can curdle in acidic coffee."),
    ("d24", "How to Store Coffee Beans",
     "Store beans in an airtight container away from light and heat. "
     "Buy small batches often instead of stocking up."),
    ("d25", "Freezing Coffee Beans",
     "Freezing works if beans are sealed airtight and portioned; never "
     "refreeze thawed beans, and grind straight from frozen."),
    ("d26", "How Long Do Beans Stay Fresh",
     "Whole beans peak within a month of roasting. Ground coffee stales "
     "within minutes of grinding, so grind right before brewing."),
    ("d27", "Aeropress Inverted Method",
     "Flip the brewer upside down, add grounds and water, steep, then flip "
     "onto your cup and press. No drips before you are ready."),
    ("d28", "Aeropress Recipes Compared",
     "Championship recipes vary wildly: some use 80 degree water, others "
     "near-boiling, with steep times from 1 to 3 minutes."),
    ("d29", "Travel Coffee Kits",
     "An Aeropress, a hand grinder, and a small scale make a capable "
     "travel coffee setup that fits in a backpack."),
    # Tied pair: identical title and text -> identical BM25 scores.
    ("d30", "Coffee Storage Basics",
     "Keep coffee beans in an airtight container away from light, heat, and "
     "moisture. Buy small batches and grind fresh for the best flavor."),
    ("d31", "Coffee Storage Basics",
     "Keep coffee beans in an airtight container away from light, heat, and "
     "moisture. Buy small batches and grind fresh for the best flavor."),
    ("d32", "Decaf Coffee Options",
     "Swiss water process decaffeinated beans keep more flavor than solvent "
     "methods. Decaf brews exactly like regular coffee."),
    ("d33", "Reusable Metal Filters",
     "Metal filters pass more oils and fine sediment than paper, giving a "
     "heavier body in pour over and Aeropress brewing."),
    ("d34", "Coffee Cupping Protocol",
     "Cupping scores fragrance, flavor, acidity, body, and aftertaste on a "
     "standardized form so tasters can compare coffees."),
    ("d35", "Roast Levels Explained",
     "Light roasts keep origin character; dark roasts trade it for "
     "roast-driven bitterness and heavier body."),
    ("d36", "Coffee and Health",
     "Moderate coffee consumption is associated with several benefits in "
     "large observational studies, though effects vary by person."),
]

# d12 is indexed a second time (re-ingestion duplicate, same logical doc_id).
EXTRA_INDEX_IDS = {"d12": ["d12", "d12_reingest"]}

QUERIES = [
    ("q01", "pour over coffee brewing"),
    ("q02", "espresso machine pressure"),
    ("q03", "cold brew steep time"),
    ("q04", "burr vs blade grinder"),
    ("q05", "water temperature for brewing"),
    ("q06", "decaffeinated mushroom jerky"),
    ("q07", "french press coffee ratio"),
    ("q08", "milk frothing temperature"),
    ("q09", "coffee storage freshness"),
    ("q10", "aeropress inverted method"),
]

# (query_id, doc_id, grade, judge)
JUDGMENTS = [
    ("q01", "d01", 3, "alice"), ("q01", "d02", 2, "alice"),
    ("q01", "d03", 2, "alice"), ("q01", "d04", 1, "alice"),
    ("q01", "d13", 0, "alice"), ("q01", "d33", 0, "alice"),
    ("q02", "d05", 3, "alice"), ("q02", "d07", 2, "alice"),
    ("q02", "d06", 2, "alice"), ("q02", "d08", 1, "alice"),
    ("q02", "d04", 0, "alice"),
    ("q03", "d09", 3, "alice"), ("q03", "d10", 2, "alice"),
    ("q03", "d11", 1, "alice"), ("q03", "d16", 1, "alice"),
    ("q03", "d28", 0, "alice"),
    ("q04", "d15", 3, "alice"), ("q04", "d17", 2, "alice"),
    ("q04", "d16", 1, "alice"), ("q04", "d29", 0, "alice"),
    ("q05", "d12", 3, "bob"), ("q05", "d13", 2, "bob"),
    ("q05", "d14", 2, "bob"), ("q05", "d21", 1, "bob"),
    ("q05", "d28", 0, "bob"),
    # q06: every judged candidate is non-relevant -> zero-relevant query.
    ("q06", "d32", 0, "alice"), ("q06", "d34", 0, "alice"),
    ("q06", "d36", 0, "alice"),
    ("q07", "d18", 3, "alice"), ("q07", "d19", 2, "alice"),
    ("q07", "d20", 1, "alice"), ("q07", "d16", 1, "alice"),
    ("q07", "d04", 0, "alice"),
    ("q08", "d21", 3, "bob"), ("q08", "d22", 2, "bob"),
    ("q08", "d23", 1, "bob"), ("q08", "d13", 0, "bob"),
    ("q09", "d24", 2, "bob"), ("q09", "d25", 2, "bob"),
    ("q09", "d26", 3, "bob"), ("q09", "d30", 3, "bob"),
    ("q09", "d31", 3, "bob"), ("q09", "d35", 0, "bob"),
    ("q10", "d27", 3, "alice"), ("q10", "d28", 2, "alice"),
    ("q10", "d29", 1, "alice"), ("q10", "d33", 0, "alice"),
]

EXPERIMENTS = [
    {
        "name": "title-boost-v2",
        "description": "Boost title matches 3x over body text.",
        "baseline_config": {"type": "match", "field": "text"},
        "treatment_config": {"type": "multi_match",
                             "fields": ["title^3", "text"],
                             "tie_breaker": 0.3},
        "run": True,
    },
    {
        "name": "phrase-ranking",
        "description": "Phrase matching instead of bag-of-words. "
                       "Runs intentionally left unexecuted.",
        "baseline_config": {"type": "match", "field": "text"},
        "treatment_config": {"type": "match_phrase", "field": "text"},
        "run": False,
    },
]


def seed() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        # Wipe previous seed data (cascades to runs/results/metrics).
        for model in (models.Judgment, models.JudgmentSet, models.Judge,
                      models.Experiment, models.Query):
            db.query(model).delete()
        db.commit()

        # Index the corpus.
        client = retrieval.get_client()
        retrieval.ensure_index(client, INDEX)
        docs = []
        for doc_id, title, text in DOCS:
            for index_id in EXTRA_INDEX_IDS.get(doc_id, [doc_id]):
                docs.append({"_id": index_id, "doc_id": doc_id,
                             "title": title, "text": text})
        retrieval.index_docs(client, INDEX, docs)

        judges = {}
        for name in sorted({j[3] for j in JUDGMENTS}):
            judge = models.Judge(name=name)
            db.add(judge)
            judges[name] = judge
        db.flush()

        for qid, text in QUERIES:
            db.add(models.Query(id=qid, text=text))

        jset = models.JudgmentSet(
            name="coffee-qrels", version="v1",
            description="Synthetic coffee-brewing judgments, grades 0-3. "
                        "Judges: alice, bob.")
        db.add(jset)
        db.flush()
        for qid, doc_id, grade, judge_name in JUDGMENTS:
            db.add(models.Judgment(
                judgment_set_id=jset.id, query_id=qid, doc_id=doc_id,
                grade=grade, judge_id=judges[judge_name].id))

        for spec in EXPERIMENTS:
            exp = models.Experiment(
                name=spec["name"], description=spec["description"],
                judgment_set_id=jset.id, index_name=INDEX,
                baseline_config=spec["baseline_config"],
                treatment_config=spec["treatment_config"])
            db.add(exp)
            db.flush()
            if spec["run"]:
                for role in ("baseline", "treatment"):
                    run = services.execute_run(db, exp, role, client=client)
                    if run.status != "completed":
                        raise RuntimeError(f"seed run failed: {run.error}")
        db.commit()
        print("seed complete")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
