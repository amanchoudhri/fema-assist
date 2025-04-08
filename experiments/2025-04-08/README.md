# field notes 2025-04-08

Set up and tried an *evaluation* pipeline to check the correctness of a JSON
representation of a FEMA disaster declaration request form (Form 010-0-13).

## Pipeline
Defined in `check.yaml`. Goal: check whether each field is correctly transcribed,
and whether all fields are included.
- prompt includes the JSON repr of a disaster declaration request and the actual form PDF
- asks `gemini-2.0-flash` to verify each field (currently *all in one prompt*), outputting
  an assessment of correctness and a description of why/why not in the following structure:
  ```text
  <FIELD field_name>
      is_accurate: bool
      discussion: str
  <\FIELD>
  ```
- splits on the closing tag `<\FIELD>`, parses each chunk to JSON, then aggregates together
  and calculates accuracy.

Output for each form is formatted as:
```json
{
"field_analyses": [
  {
    "field_name": "resource_description",
    "is_accurate": true,
    "discussion": "Correctly captured",
    "field_value": "The State of Alaska has executed its Emergency Operations Plans and committed all available State and local resources to the response and recovery from this event. The State of Alaska will provide the full 25% non-federal cost share and will work with each affected jurisdiction to cover any expenses not included in a federal declaration."
  },
  {
    "field_name": "incident_type",
    "is_accurate": true,
    "discussion": "Correctly captured",
    "field_value": [
      "earthquake"
    ]
  },
  {
    "field_name": "request_purpose",
    "is_accurate": true,
    "discussion": "Correctly captured",
    "field_value": "major disaster"
  },
  ...
  ]
}
```

## Test Details
- Ran eval pipeline on the three parsed forms from yesterday (`../2025-04-07/test-forms`)

## Results
By and large seems pretty good. Across 3 documents, reported 4 inaccurate
fields.

### Reported Inaccuracies

One inaccuracy reported seems strange. When checking `../2025-04-07/test-forms/form-3.pdf`,
the following is reported for the `snow_assistance_requested` field.
```json
{
    "field_name": "snow_assistance_requested",
    "is_accurate": false,
    "discussion": "Correctly captured",
    "field_value": false
},
```
Initially the form was parsed correctly, that no snow assistance was requested.
The `check.yaml` pipeline said instead that this is *inaccurate*, but
gave a description that nonetheless said `"Correctly captured"`.

The remaining three flagged an issue identified yesterday, where fields that should be 
left *blank* are instead being imputed with the string `"UNKNOWN"`. For example, on `../2025-04-07/test-forms/form-2.pdf`,
the following is caught:
```json
{
    "field_name": "snow_assistance_jurisdictions",
    "is_accurate": false,
    "discussion": "Should be empty string since the box is unchecked.",
    "field_value": "UNKNOWN"
},
```

### Inaccuracies Not Caught

The pipeline *missed* inaccuracies where fields that should have been left empty
were filled with the field *description* text.

For example, in `../2025-04-07/test-forms/form-3.pdf`:
```json
{
    "field_name": "direct_federal_assistance_types",
    "is_accurate": true,
    "discussion": "Correctly captured",
    "field_value": "I request the following type(s) of assistance:"
},
```
Also in that form:
```json
{
    "field_name": "direct_federal_assistance_reasons",
    "is_accurate": true,
    "discussion": "Correctly captured",
    "field_value": "List of reasons why State and local or Indian tribal government cannot perform, or contract for, required work and services."
},
```

## Thoughts
One of the reported inaccuracies, on `snow_assistance_requested`, was
erroneous. It looks like the boolean was just reported incorrectly, potentially
due to random sampling. To test this, I'll retry with lower temperature.

Another explanation is that the task of checking *all fields* in one prompt is far
too much context to expect reliable outputs. To test this, I'll manually
separate the checking task out to be page-by-page, with each field for each
page.

Simplifying the task in this way way could also help catch
problems where form field descriptions are imputed into empty fields. With more wiggle
room in the effective context window, we can maybe include an OCR representation of a blank
form (or pages of a blank form), to help catch this issue.
