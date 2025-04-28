# field notes 2025-04-28

Enhanced the parsing and evaluation pipeline for FEMA disaster declaration request forms (Form 010-0-13).

## Improvements Made

### Larger Test Set
Randomly selected 12 declarations to manually label, compiled them all into a new test set, at `test-set-truth.json`.

## Test Results

Ran detailed evaluation on the test set with the latest parsing pipeline:

- Overall Accuracy: 97.59% (527/540 fields correct)
- Checkbox Field Accuracy: 97.22% (105/108 fields)
- Multi-Select Field Accuracy: 89.58% (43/48 fields)

Full results in `report.txt`

### Common Error Types
- Partial matches in list fields (38.5% of errors)
- Checkbox errors (23.1% of errors)
- Substring and content mismatches (30.8% of errors combined)
- False positives where empty fields got filled (7.7% of errors)

### Most Problematic Fields
- `direct_federal_assistance_requested`: 83.33% accuracy
- `ia_requested_programs`: 83.33% accuracy
- `incident_type`: 83.33% accuracy

## Next Steps
Improving prompt engineering for checkbox/multi-select fields seems to be the most important goal.

Intuitively, it seems like LLM parsing tends to do best when we really minimize the processing
they have to do and really turn the task into one that statistical co-occurence would solve well.
Rather than returning a list of enum options for multi-select, then, maybe LLMs would do better
if they had T/F options for each checkbox.

## Thoughts
Checkbox detection remains challenging but has improved. The most
significant issue seems to be with multi-select fields where LLMs struggle with
completeness (capturing all options).
