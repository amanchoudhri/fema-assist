# field notes 2025-04-30

Experiment testing LLM-based form filling for FEMA Form 010-0-13 using PDA reports as input.

## Implementation

Created a simple form fill system that:
- Takes PDA reports as input
- Prompts LLM as "ex-FEMA official working at Hagerty Consulting"
- Fills out form in batches of $N$ fields per inference request
- Uses JSON schema validation for outputs

Tested the system on the 12 manually validated forms in the test set. Code
available at `src/fema_agent/simple_form_fill.py`; outputted form attempts
available at `form-filled-N-15.json` and `form-filled-N-5.json`.

## Results

### Comparison: N=15 vs N=5

| Metric | N=15 | N=5 |
|--------|------|-----|
| Overall Accuracy | 16.30% (88/540) | 16.30% (88/540) |
| Checkbox Accuracy | 25.93% (28/108) | 23.15% (25/108) |
| Multi-select Accuracy | 0.00% (0/48) | 0.00% (0/48) |
| Total Errors | 452 | 452 |

Full results available in `experiments/2025-04-30/results-N-5.txt` and
`experiments/2025-04-30/results-N-15.txt`.

### Error Distribution

| Error Type | N=15 | N=5 |
|------------|------|-----|
| Type mismatch | 43.4% | 33.4% |
| Content mismatch | 24.3% | 28.5% |
| Checkbox error | 17.7% | 18.4% |
| Format error | 8.0% | 7.7% |
| False positive | 2.0% | 7.7% |
| Complete mismatch | 2.7% | 2.9% |
| Substring match | 2.0% | 1.3% |

### Worst Performing Fields
30 fields had 0% accuracy across both configurations, including all multi-select fields.

## Observations

1. Field count per request did not meaningfully impact overall accuracy - suggests the issue is not context length / task complexity
2. PDA reports lack sufficient information for many required form fields
3. Multi-select fields are particularly challenging regardless of fields/request

## Next Steps
Many low-hanging prompting fruits, including:
 - Few-shot examples to demonstrate correct form filling
 - Including FEMA documentation into context.
 - Providing more guidance on form output structure (to improve parsing, especially of enums)
