import time
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from core import (
    QUERIES,
    SERPER_API_KEY,
    TELEGRAM_API_ID,
    TELEGRAM_API_HASH,
    TELEGRAM_SEARCH_TERMS,
    apply_scoring,
    ensure_columns,
    extract_possible_handle,
    filter_ranked_results,
    query_matches_filters,
    run_telegram_fetch,
    serper_search,
)

st.set_page_config(page_title="Finance Lead Discovery", layout="wide")
st.title("Finance Lead Discovery")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Configuration")

    st.subheader("API Keys")
    serper_ok = bool(SERPER_API_KEY)
    st.markdown(f"{'🟢' if serper_ok else '🔴'} **Serper** {'loaded' if serper_ok else 'missing — add to .env'}")
    tg_ok = bool(TELEGRAM_API_ID and TELEGRAM_API_HASH)
    st.markdown(f"{'🟢' if tg_ok else '🔴'} **Telegram** {'loaded' if tg_ok else 'optional — add to .env'}")

    st.divider()

    with st.expander("Filters", expanded=True):
        min_score = st.slider("Min commercial score", 0, 70, 20)
        include_high_risk = st.checkbox("Include high-risk leads", value=False)
        target_platforms = st.multiselect(
            "Platforms",
            ["facebook", "instagram", "tiktok", "telegram", "other"],
            default=["facebook", "instagram", "tiktok", "telegram"],
        )
        target_use_cases = st.multiselect(
            "Use cases",
            ["forex_educator", "signal_provider", "introducing_broker", "money_manager", "mirror_trading"],
            default=["forex_educator", "signal_provider", "introducing_broker", "money_manager", "mirror_trading"],
        )
        target_assets = st.multiselect(
            "Assets",
            ["forex", "gold", "stocks", "indices", "crypto_optional"],
            default=["forex", "gold", "stocks"],
        )
        max_results_per_query = st.number_input("Results per query", min_value=1, max_value=10, value=10)
        delay = st.number_input("Delay between queries (s)", min_value=0.5, max_value=5.0, value=1.2, step=0.1)

    with st.expander("Telegram (optional)", expanded=False):
        enable_telegram = st.checkbox("Enable Telegram fetch", value=False, disabled=not tg_ok)
        if not tg_ok:
            st.caption("Set TELEGRAM_API_ID, TELEGRAM_API_HASH in .env to enable.")
        channels_input = st.text_area(
            "Channel usernames (one per line)",
            placeholder="@example_channel\nhttps://t.me/example",
            height=100,
        )
        recent_limit = st.number_input("Recent messages per channel", min_value=10, max_value=500, value=100)
        search_limit = st.number_input("Search results per term", min_value=5, max_value=100, value=30)

# ---------------------------------------------------------------------------
# Run button
# ---------------------------------------------------------------------------

run_clicked = st.button("▶ Run Discovery", type="primary", disabled=not serper_ok)

if not serper_ok:
    st.info("Add your `SERPER_API_KEY` to the `.env` file and restart the app to run discovery.")

# ---------------------------------------------------------------------------
# Discovery pipeline
# ---------------------------------------------------------------------------

if run_clicked:
    all_rows = []

    with st.status("Running Serper search...", expanded=True) as status:
        active_queries = [
            e for e in QUERIES
            if query_matches_filters(e, target_platforms, target_use_cases, target_assets)
        ]
        st.write(f"Running {len(active_queries)} / {len(QUERIES)} queries matching your filters.")
        progress = st.progress(0)
        total = len(active_queries)

        for i, entry in enumerate(active_queries):
            query = entry["q"]
            st.write(f"Querying: `{query}`")
            try:
                rows = serper_search(query, num=int(max_results_per_query))
                all_rows.extend(rows)
                time.sleep(delay)
            except Exception as exc:
                st.warning(f"Query failed: {query} — {exc}")
            progress.progress((i + 1) / total if total else 1)

        raw_results = pd.DataFrame(all_rows)
        if not raw_results.empty:
            raw_results = raw_results.drop_duplicates(subset=["link"]).reset_index(drop=True)

        st.write(f"Search complete — {len(raw_results)} unique results.")

        if enable_telegram and tg_ok:
            channels = [c.strip() for c in channels_input.splitlines() if c.strip()]
            if channels:
                st.write(f"Fetching Telegram ({len(channels)} channels)...")
                try:
                    tg_df = run_telegram_fetch(
                        channels, TELEGRAM_SEARCH_TERMS,
                        int(recent_limit), int(search_limit),
                        warn_fn=st.warning,
                    )
                    st.write(f"Telegram: {len(tg_df)} rows fetched.")
                    if not tg_df.empty:
                        raw_results = pd.concat([raw_results, tg_df], ignore_index=True)
                        raw_results = raw_results.drop_duplicates(subset=["link", "snippet"]).reset_index(drop=True)
                except Exception as exc:
                    st.error(f"Telegram fetch failed: {exc}")
            else:
                st.write("No Telegram channels entered.")

        st.write("Scoring results...")
        ranked = apply_scoring(raw_results) if not raw_results.empty else pd.DataFrame()
        filtered = filter_ranked_results(
            ranked, target_platforms, include_high_risk, min_score, target_use_cases, target_assets
        ) if not ranked.empty else pd.DataFrame()

        status.update(label="Done!", state="complete")

    st.session_state["ranked"] = ranked
    st.session_state["filtered"] = filtered
    st.session_state["raw"] = raw_results

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

if "filtered" in st.session_state and not st.session_state["filtered"].empty:
    ranked = st.session_state["ranked"]
    filtered = st.session_state["filtered"]

    st.caption(f"{len(filtered)} filtered leads · {len(ranked)} total scored")

    tab_leads, tab_stats, tab_telegram = st.tabs(["Leads", "Stats", "Telegram"])

    display_cols = [
        "lead_quality", "commercial_fit_score", "compliance_risk",
        "primary_use_case", "recommended_action", "platform",
        "title", "snippet", "link", "score_reasons",
    ]

    with tab_leads:
        show_cols = [c for c in display_cols if c in filtered.columns]
        st.dataframe(
            filtered[show_cols],
            use_container_width=True,
            hide_index=True,
            column_config={"link": st.column_config.LinkColumn("link")},
        )

    with tab_stats:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Use case distribution")
            if "primary_use_case" in ranked.columns:
                vc = ranked["primary_use_case"].value_counts().reset_index()
                vc.columns = ["use_case", "count"]
                st.bar_chart(vc.set_index("use_case"))
        with col2:
            st.subheader("Platform distribution")
            if "platform" in ranked.columns:
                pc = ranked["platform"].value_counts().reset_index()
                pc.columns = ["platform", "count"]
                st.bar_chart(pc.set_index("platform"))

        if "platform" in ranked.columns and "lead_quality" in ranked.columns:
            st.subheader("Lead quality by platform")
            crosstab = pd.crosstab(ranked["platform"], ranked["lead_quality"])
            fig, ax = plt.subplots(figsize=(9, 4))
            crosstab.plot(kind="bar", stacked=True, ax=ax)
            ax.set_xlabel("Platform")
            ax.set_ylabel("Count")
            ax.legend(title="Lead Quality")
            plt.tight_layout()
            st.pyplot(fig)

    with tab_telegram:
        tg_leads = ranked[ranked["platform"] == "telegram"].copy() if "platform" in ranked.columns else pd.DataFrame()
        if tg_leads.empty:
            st.info("No Telegram leads found in this run.")
        else:
            tg_cols = [c for c in ["lead_quality", "commercial_fit_score", "primary_use_case", "title", "link"] if c in tg_leads.columns]
            st.dataframe(
                tg_leads[tg_cols],
                use_container_width=True,
                hide_index=True,
                column_config={"link": st.column_config.LinkColumn("link")},
            )

    # ---------------------------------------------------------------------------
    # Export
    # ---------------------------------------------------------------------------

    st.divider()
    st.subheader("Export")

    FINAL_COLS = [
        "lead_score", "lead_quality", "commercial_fit_score", "compliance_risk",
        "recommended_action", "primary_use_case", "finance_use_cases", "asset_interest",
        "region_hits", "review_status", "platform", "title", "snippet",
        "manual_visible_text", "matched_terms", "score_reasons", "risk_reasons",
        "link", "source_query", "notes",
    ]

    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        st.caption("**Lead quality**")
        exp_quality_options = ["low", "medium", "high", "very_high"]
        exp_quality_selected = [
            q for q in exp_quality_options
            if st.checkbox(q, value=(q in ["high", "very_high"]), key=f"exp_q_{q}")
        ]
    with exp_col2:
        st.caption("**Platforms**")
        exp_platform_options = ["facebook", "instagram", "tiktok", "telegram", "other"]
        exp_platforms_selected = [
            p for p in exp_platform_options
            if st.checkbox(p, value=True, key=f"exp_p_{p}")
        ]

    export_df = filtered.copy()
    if exp_quality_selected:
        export_df = export_df[export_df["lead_quality"].astype(str).isin(exp_quality_selected)]
    if exp_platforms_selected:
        export_df = export_df[export_df["platform"].isin(exp_platforms_selected)]

    export_df["possible_handle_or_page"] = export_df["link"].apply(extract_possible_handle)
    export_df["action_status"] = "research_more"
    export_df = ensure_columns(export_df, FINAL_COLS)
    final_cols_present = ["possible_handle_or_page", "action_status"] + [c for c in FINAL_COLS if c in export_df.columns]
    export_df = export_df[final_cols_present].sort_values("commercial_fit_score", ascending=False)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    st.download_button(
        label=f"Download filtered leads ({len(export_df)} rows)",
        data=export_df.to_csv(index=False, encoding="utf-8-sig"),
        file_name=f"finance_leads_{timestamp}.csv",
        mime="text/csv",
        disabled=export_df.empty,
    )

elif "filtered" in st.session_state and st.session_state["filtered"].empty:
    st.warning("No leads matched the current filters. Try lowering the min score or broadening platform/use-case filters.")
