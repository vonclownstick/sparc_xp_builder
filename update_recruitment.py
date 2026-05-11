import csv
import random
import os
import shutil
import sys
import argparse
from datetime import datetime

def get_constants():
    c = {}
    if not os.path.exists('CONSTANTS.txt'):
        return None
    with open('CONSTANTS.txt', 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                parts = line.strip().split('=')
                if len(parts) == 2:
                    k, v = parts
                    try:
                        c[k] = float(v)
                    except ValueError:
                        c[k] = v
    return c

def save_csv(data, fieldnames, filename):
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(data)

def get_yield(rows, stratum, site=None, constants=None):
    """
    Get yield for a stratum.

    Priority:
    1. Calculated from historical data (if any invites exist for this stratum)
    2. Site-specific default (e.g., MGB_S1_YIELD=0.15)
    3. Generic stratum default (e.g., S1_YIELD=0.20)
    4. Hard-coded default of 0.1
    """
    # First, try to calculate from historical data
    s_rows = [r for r in rows if r['stratum'] == stratum]
    invited = [r for r in s_rows if r['status'] != 'Not Invited']
    if invited:
        completed = [r for r in invited if r['status'] == 'Completed']
        return max(len(completed) / len(invited), 0.01)  # Avoid division by zero

    # No historical data - fall back to configured defaults
    if constants and site:
        site_key = f'{site}_{stratum}_YIELD'
        if site_key in constants:
            return float(constants[site_key])

    if constants:
        generic_key = f'{stratum}_YIELD'
        if generic_key in constants:
            return float(constants[generic_key])

    return 0.1  # Hard-coded default if nothing else specified

def stratified_site_select(rows, site_target, pool_filter, strata, weights, yields_per_stratum, log_messages, log_prefix=""):
    """
    Stratified random selection from `rows`, filtered by `pool_filter`, totaling `site_target`,
    using weights and yields to allocate per stratum, with cascade for shortfalls.
    Mutates `log_messages` and returns the list of selected rows.
    """
    adjusted_weights = {s: weights[s] / yields_per_stratum[s] for s in strata}
    total_adj_w = sum(adjusted_weights.values())
    normalized_weights = {s: adjusted_weights[s] / total_adj_w for s in strata}

    float_targets = {s: site_target * normalized_weights[s] for s in strata}
    floor_targets = {s: int(v) for s, v in float_targets.items()}
    remainder = site_target - sum(floor_targets.values())
    fractional_parts = {s: v - int(v) for s, v in float_targets.items()}
    sorted_strata = sorted(fractional_parts.keys(), key=lambda k: fractional_parts[k], reverse=True)
    for i in range(remainder):
        floor_targets[sorted_strata[i]] += 1

    selected_all = []
    carryover = 0
    for idx, s in enumerate(strata):
        original_target = floor_targets[s]
        s_target = original_target + carryover

        eligible_rows = [r for r in rows if r['stratum'] == s and pool_filter(r)]
        available = len(eligible_rows)

        if carryover > 0:
            log_messages.append(f"  {log_prefix}{s}: Yield={yields_per_stratum[s]:.2f}, Base Target={original_target}, +Cascade={carryover}, Total Target={s_target}, Available={available}")
        else:
            log_messages.append(f"  {log_prefix}{s}: Yield={yields_per_stratum[s]:.2f}, Target={s_target}, Available={available}")

        if available <= s_target:
            selected = eligible_rows
            shortfall = s_target - available
            if shortfall > 0 and idx < len(strata) - 1:
                next_s = strata[idx + 1]
                log_messages.append(f"    WARNING: Ran out of {s}, shifting {shortfall} to {next_s}")
                carryover = shortfall
            elif shortfall > 0:
                log_messages.append(f"    WARNING: Ran out of {s}, {shortfall} unfilled (no more strata)")
                carryover = 0
            else:
                carryover = 0
        else:
            selected = random.sample(eligible_rows, s_target)
            carryover = 0

        selected_all.extend(selected)
        log_messages.append(f"    Added: {len(selected)}")

    return selected_all

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--visits", type=int, default=None,
                        help="Number of fresh letter-1 invites to generate")
    parser.add_argument("--catchup_list2", type=int, default=None,
                        help="Number of letter-2 catchup invites to generate from people who got letter 1 but are not on the prior list")
    parser.add_argument("--prior_list", type=str)
    parser.add_argument("--allow-single-site", action="store_true",
                        help="Allow running with only one site's master file present")
    parser.add_argument("--yield", type=float, dest="fixed_yield", default=None,
                        help="Override all yield calculations with a fixed value (e.g. --yield 0.05)")
    parser.add_argument("--weights", type=str, default=None,
                        help="Override stratum weights S1-S6 as comma-separated values (e.g. --weights 0.55,0.20,0.00,0.10,0.07,0.08)")
    args = parser.parse_args()

    if args.visits is None and args.catchup_list2 is None:
        print("Error: must specify --visits N and/or --catchup_list2 N.")
        return

    if args.visits is not None and args.catchup_list2 is not None:
        print(f"You requested BOTH a fresh letter-1 batch ({args.visits}) and a letter-2 catchup batch ({args.catchup_list2}).")
        ans = input("Proceed? [Y/N]: ")
        if ans.lower() != 'y':
            return

    # Parse and validate weight overrides
    weight_overrides = None
    if args.weights:
        parts = args.weights.split(',')
        if len(parts) != 6:
            print("Error: --weights requires exactly 6 comma-separated values (S1 through S6).")
            return
        try:
            weight_overrides = {f'S{i+1}': float(parts[i]) for i in range(6)}
        except ValueError:
            print("Error: --weights values must be numeric.")
            return
        total = sum(weight_overrides.values())
        if abs(total - 1.0) > 0.01:
            print(f"Warning: weights sum to {total:.4f}, normalizing to 1.0")
            weight_overrides = {s: w / total for s, w in weight_overrides.items()}

    C = get_constants()
    output_dir = C.get('OUTPUT_DIR', 'study_data/outputs')
    backup_dir = C.get('BACKUP_DIR', 'study_data/backups')
    log_dir = C.get('LOG_DIR', 'study_data/logs')

    mgb_path = os.path.join(output_dir, 'parsed_mgb_master_list.csv')
    vumc_path = os.path.join(output_dir, 'parsed_vumc_master_list.csv')

    mgb_exists = os.path.exists(mgb_path)
    vumc_exists = os.path.exists(vumc_path)

    if not mgb_exists and not vumc_exists:
        print("Error: No master lists found. Run update_master.py for at least one site first.")
        return

    if not (mgb_exists and vumc_exists):
        missing_site = "MGB" if not mgb_exists else "VUMC"
        present_site = "VUMC" if not mgb_exists else "MGB"
        if not args.allow_single_site:
            print(f"Warning: Only {present_site} master list found. {missing_site} master list is missing.")
            print("Use --allow-single-site to proceed with a single site.")
            return
        else:
            print(f"Note: Running with {present_site} only (--allow-single-site enabled).")

    mgb_rows = []
    vumc_rows = []
    if mgb_exists:
        with open(mgb_path, 'r') as f:
            mgb_rows = list(csv.DictReader(f))
    if vumc_exists:
        with open(vumc_path, 'r') as f:
            vumc_rows = list(csv.DictReader(f))

    # Handle Prior List and Contact Stage Advancement
    # AIDEV-NOTE: Stage progression: -1 (never contacted) → 1 (initial letter) → 2 (follow-up) → 3 (final letter) → removed
    # AIDEV-NOTE: Stage advancement (1→2, 2→3) and letter-date stamping are DEFERRED until after output selection
    # so that anyone dropped from an output list does not get falsely marked as having received a letter.
    # Status updates from the research team and stage-3 closeout still apply unconditionally.
    holdovers = []           # Prior-list rows still active, will appear on regular output
    advance_to_2 = []        # Stage-1 prior-list rows with letter1_date set (will advance unless picked by catchup)
    advance_to_3 = []        # Stage-2 prior-list rows with letter2_date >28d (will advance to stage 3)
    held_at_1 = 0            # Stage-1 prior-list rows missing letter1_date (no advance, no letter recorded)
    held_at_2 = 0
    removed_stage3 = 0
    prior_map = {}
    today_str = datetime.now().strftime('%Y-%m-%d')

    if not args.prior_list:
        ans = input("There is no prior list provided, do you want to proceed? [Y/N]: ")
        if ans.lower() != 'y':
            sys.exit()
    else:
        if os.path.exists(args.prior_list):
            with open(args.prior_list, 'r') as f:
                prior_rows = list(csv.DictReader(f))

            # Create maps for quick lookup of updates
            # We update status, letter1_date, letter2_date
            prior_map = {r['offspring_MRN']: r for r in prior_rows}

            def update_rows(rows, p_map):
                for r in rows:
                    mrn = r['offspring_MRN']
                    if mrn in p_map:
                        p_row = p_map[mrn]
                        if 'status' in p_row and p_row['status']:
                            r['status'] = p_row['status']
                        if 'letter1_date' in p_row:
                            r['letter1_date'] = p_row['letter1_date']
                        if 'letter2_date' in p_row:
                            r['letter2_date'] = p_row['letter2_date']
                        if 'letter3_date' in p_row:
                            r['letter3_date'] = p_row['letter3_date']

            update_rows(mgb_rows, prior_map)
            update_rows(vumc_rows, prior_map)

            # Identify advancement candidates and holdovers — do NOT apply stage/date changes yet.
            # Stage-3 closeout IS applied immediately (it's a closeout, not a mailing action).
            RESOLVED_STATUSES = {'Completed', 'Consented', 'Refused'}

            for r in mgb_rows + vumc_rows:
                mrn = r['offspring_MRN']
                if mrn not in prior_map:
                    continue

                status = r.get('status', 'Pending')
                if status in RESOLVED_STATUSES:
                    continue

                stage = int(r.get('contact_stage', '-1'))

                if stage == 3:
                    # Exhausted all 3 contacts — closeout (unconditional, no mailing action)
                    r['status'] = 'No Response - 3 Letters'
                    removed_stage3 += 1
                    continue

                if stage == 2:
                    letter2 = r.get('letter2_date', '')
                    if letter2:
                        days_since = (datetime.now() - datetime.strptime(letter2, '%Y-%m-%d')).days
                        if days_since > 28:
                            advance_to_3.append(r)
                            holdovers.append(r)
                        else:
                            holdovers.append(r)
                            held_at_2 += 1
                    else:
                        # No letter2_date stamped — letter 2 was never sent; stay at stage 2 awaiting catchup_list2.
                        holdovers.append(r)
                        held_at_2 += 1
                    continue

                if stage == 1:
                    letter1 = r.get('letter1_date', '')
                    if letter1:
                        # Letter 1 was sent — eligible to advance to stage 2.
                        advance_to_2.append(r)
                        holdovers.append(r)
                    else:
                        # No letter1_date stamped — letter 1 was never sent; stay at stage 1.
                        holdovers.append(r)
                        held_at_1 += 1
                    continue

            print(f"Prior-list summary: {len(advance_to_2)} eligible to advance 1→2, "
                  f"{len(advance_to_3)} eligible to advance 2→3, {held_at_1} held at stage 1 (no letter 1 stamped), "
                  f"{held_at_2} held at stage 2, {removed_stage3} closed out (no response after 3 letters)")
        else:
            print(f"Error: Prior list {args.prior_list} not found.")
            return

    mgb_ratio = C.get('MGB_RATIO', 0.6667)

    def build_site_configs(total_needed):
        if mgb_rows and vumc_rows:
            mgb_target = int(total_needed * mgb_ratio + 0.5)
            vumc_target = total_needed - mgb_target
            return [
                {'site': 'MGB', 'rows': mgb_rows, 'target': mgb_target},
                {'site': 'VUMC', 'rows': vumc_rows, 'target': vumc_target},
            ]
        if mgb_rows:
            return [{'site': 'MGB', 'rows': mgb_rows, 'target': total_needed}]
        if vumc_rows:
            return [{'site': 'VUMC', 'rows': vumc_rows, 'target': total_needed}]
        return []

    strata = [f'S{i}' for i in range(1, 7)]
    if weight_overrides:
        weights = weight_overrides
        print(f"Using weight overrides: {', '.join(f'{s}={w:.2f}' for s, w in weights.items())}")
    else:
        weights = {s: C.get(f'{s}_WEIGHT', 0.1) for s in strata}

    log_messages = []
    log_messages.append(f"Recruitment Update - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if weight_overrides:
        log_messages.append(f"  NOTE: Using weight overrides: {', '.join(f'{s}={w:.2f}' for s, w in weight_overrides.items())}")
    if prior_map:
        log_messages.append(f"  Prior-list: {len(advance_to_2)} eligible 1→2, {len(advance_to_3)} eligible 2→3, "
                            f"{held_at_1} held at 1, {held_at_2} held at 2, {removed_stage3} closed out (3 letters, no response)")
    if holdovers:
        log_messages.append(f"  Holdovers on regular output: {len(holdovers)}")

    # === --visits: fresh letter-1 selection ===
    new_selections = []
    if args.visits is not None:
        total_needed = args.visits
        print(f"Total target (Fresh Invites): {total_needed}")
        if holdovers:
            print(f"Continuing contacts from prior list: {len(holdovers)}")

        for config in build_site_configs(total_needed):
            site = config['site']
            rows = config['rows']
            site_new_needed = config['target']

            log_messages.append(f"\nSite: {site} (Target New Letter-1: {site_new_needed})")

            if args.fixed_yield is not None:
                yields = {s: args.fixed_yield for s in strata}
                log_messages.append(f"  NOTE: Using fixed yield override: {args.fixed_yield}")
            else:
                yields = {s: get_yield(rows, s, site=site, constants=C) for s in strata}

            site_selected = stratified_site_select(
                rows, site_new_needed,
                pool_filter=lambda r: r['status'] == 'Not Invited' and r['eligible'] == '1',
                strata=strata, weights=weights, yields_per_stratum=yields,
                log_messages=log_messages,
            )
            new_selections.extend(site_selected)
            log_messages.append(f"  SITE SUMMARY: Target={site_new_needed}, Selected={len(site_selected)}, Unfilled={site_new_needed - len(site_selected)}")

        unfilled = total_needed - len(new_selections)
        log_messages.append(f"\n=== LETTER-1 GRAND TOTAL: Target={total_needed}, Selected={len(new_selections)}, Unfilled={unfilled} ===")
        if unfilled > 0:
            log_messages.append(f"WARNING: Could not fill {unfilled} letter-1 slots — insufficient eligible participants across all strata")

    # === --catchup_list2: stratified letter-2 catchup selection ===
    # AIDEV-NOTE: Pool is master rows at stage 1 with letter1_date stamped (i.e., letter 1 was sent),
    # excluding anyone already in prior_map (those auto-advance via the regular output).
    catchup_selections = []
    if args.catchup_list2 is not None:
        total_catchup = args.catchup_list2
        print(f"Letter-2 catchup target: {total_catchup}")

        for config in build_site_configs(total_catchup):
            site = config['site']
            rows = config['rows']
            site_catchup_target = config['target']

            log_messages.append(f"\nSite: {site} (Target Letter-2 Catchup: {site_catchup_target})")

            if args.fixed_yield is not None:
                yields = {s: args.fixed_yield for s in strata}
            else:
                yields = {s: get_yield(rows, s, site=site, constants=C) for s in strata}

            site_selected = stratified_site_select(
                rows, site_catchup_target,
                pool_filter=lambda r: (r['status'] == 'Pending'
                                       and r.get('contact_stage', '') == '1'
                                       and r.get('letter1_date', '') != ''
                                       and r['eligible'] == '1'
                                       and r['offspring_MRN'] not in prior_map),
                strata=strata, weights=weights, yields_per_stratum=yields,
                log_messages=log_messages, log_prefix='Catchup ',
            )
            catchup_selections.extend(site_selected)
            log_messages.append(f"  SITE SUMMARY: Target={site_catchup_target}, Selected={len(site_selected)}, Unfilled={site_catchup_target - len(site_selected)}")

        unfilled = total_catchup - len(catchup_selections)
        log_messages.append(f"\n=== LETTER-2 CATCHUP TOTAL: Target={total_catchup}, Selected={len(catchup_selections)}, Unfilled={unfilled} ===")
        if unfilled > 0:
            log_messages.append(f"WARNING: Could not fill {unfilled} letter-2 catchup slots — insufficient stage-1 participants with letter1_date stamped")

    # === Apply state changes (DEFERRED so anyone not on an output list is never falsely advanced) ===
    for r in advance_to_2:
        r['contact_stage'] = '2'
        r['letter2_date'] = today_str
        r['last_contact_date'] = today_str

    for r in advance_to_3:
        r['contact_stage'] = '3'
        r['letter3_date'] = today_str
        r['last_contact_date'] = today_str

    for r in catchup_selections:
        r['contact_stage'] = '2'
        r['letter2_date'] = today_str
        r['last_contact_date'] = today_str

    for r in new_selections:
        r['status'] = 'Pending'
        r['contact_stage'] = '1'
        r['last_contact_date'] = today_str
        r['date_added_to_recruitment'] = today_str
        r['letter1_date'] = today_str
        r['letter2_date'] = ''
        r['letter3_date'] = ''

    # === Save master (single write, after all state changes) ===
    if mgb_rows:
        save_csv(mgb_rows, list(mgb_rows[0].keys()), mgb_path)
    if vumc_rows:
        save_csv(vumc_rows, list(vumc_rows[0].keys()), vumc_path)

    # === Write output files ===
    random.shuffle(new_selections)
    regular_output = holdovers + new_selections

    today_ts = datetime.now().strftime('%Y%m%d')
    blinded_fields = ['model_score', 'model_pctile', 'stratum']

    def output_fieldnames(rows):
        fn = [f for f in rows[0].keys() if f not in blinded_fields and 'diagnosis' not in f.lower()]
        for f in ['date_added_to_recruitment', 'letter1_date', 'letter2_date', 'letter3_date', 'contact_stage']:
            if f not in fn:
                fn.append(f)
        return fn

    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    now_hm = datetime.now().strftime('%H%M')

    if regular_output:
        # AIDEV-NOTE: Recruitment list is blinded — excludes model_score, model_pctile, stratum, and diagnosis fields.
        output_path = os.path.join(output_dir, f"recruitment_{today_ts}.csv")
        save_csv(regular_output, output_fieldnames(regular_output), output_path)
        print(f"Saved recruitment list to {output_path}")
        shutil.copy(output_path, os.path.join(backup_dir, f"recruitment_{today_ts}_{now_hm}.csv"))

    if catchup_selections:
        catchup_path = os.path.join(output_dir, f"catchup_letter2_{today_ts}.csv")
        save_csv(catchup_selections, output_fieldnames(catchup_selections), catchup_path)
        print(f"Saved letter-2 catchup list to {catchup_path}")
        shutil.copy(catchup_path, os.path.join(backup_dir, f"catchup_letter2_{today_ts}_{now_hm}.csv"))

    # Logging
    log_content = "\n".join(log_messages)
    print(log_content)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    with open(os.path.join(log_dir, f"recruitment_{datetime.now().strftime('%Y%m%d')}.log"), 'a') as f:
        f.write(log_content + "\n")

if __name__ == "__main__":
    main()
