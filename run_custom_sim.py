from logic.staffing_optimizer import find_best_staffing


def main():
    starts = [f"{h:02d}:00" for h in range(5, 24)]

    print("Running optimized search for 6 officers...")
    best = find_best_staffing(
        officer_counts=[6],
        annual_hours_target=2008.0,
        annual_hours_variance=40.0,
        rotation_style="rotating",
        shift_starts_options=[starts],
        free_starts=True,
        free_lengths=True,
        free_variations=True,
    )

    if best:
        print("\n=== BEST RESULT ===")
        print(f"Shift Length: {best.get('shift_length_hours')}")
        print(f"Rotation: {best.get('rotation_name')}")
        print(f"Total Officers: {best.get('total_officers')}")
        print("Start Times:")
        for w in best.get("windows", []):
            print(f"  {w.get('start_time')} to {w.get('end_time')} ({w.get('min_officers')} officers)")
    else:
        print("No valid schedule found.")


if __name__ == "__main__":
    main()
