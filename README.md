# GradTrack 2027 – daily job lists

Every copy of GradTrack downloads two lists when it opens:

- `jobs.json` – graduate schemes (2027 starts), checked by hand against each employer's posting.
- `entry.json` – graduate and entry-level job ads in London, Birmingham, Manchester, Leeds and Liverpool, collected
  every day and filtered automatically (`tools/entry_build.py`).

Both follow the format in `SPEC.md` (entry requirements are structured so the tracker can filter by degree subject,
A-levels/UCAS points, GCSEs, degree class, location and driving licence).

Please don't edit by hand unless you know the format – an invalid file is ignored by the tracker, which then falls
back to the last good list.
