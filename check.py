import argparse
import json

import pandas as pd

from forms.fema_010_0_13 import FEMA_FORM_010_0_13

def load_data(ground_truth_path: str, attempt_path: str):
    """Load ground truth and attempt data from JSON files."""
    with open(ground_truth_path) as f:
        ground_truth = json.load(f)

    with open(attempt_path) as f:
        attempt = json.load(f)
        
    return ground_truth, attempt


def classify_error(attempt_value, truth_value, is_checkbox, is_multiselect):
    """Classify the type of error between attempt and ground truth."""
    if attempt_value == truth_value:
        return "correct"
    
    if is_checkbox:
        return "checkbox_error"  # Boolean value mismatch
    
    if is_multiselect:
        if isinstance(attempt_value, list) and isinstance(truth_value, list):
            # Check for partial overlaps
            common = set(attempt_value) & set(truth_value)
            if common:
                return "partial_match"
            return "complete_mismatch"
        return "format_error"  # One is a list, the other isn't
    
    # For string fields
    if isinstance(attempt_value, str) and isinstance(truth_value, str):
        if not truth_value and attempt_value:
            return "false_positive"  # Ground truth is empty but attempt has content
        elif truth_value and not attempt_value:
            return "false_negative"  # Ground truth has content but attempt is empty
        elif attempt_value.lower() == truth_value.lower():
            return "case_mismatch"  # Only case differences
        elif truth_value in attempt_value or attempt_value in truth_value:
            return "substring_match"  # One is contained in the other
        else:
            return "content_mismatch"  # Completely different content
    
    return "type_mismatch"  # Different data types

def preprocess_strings(string: str):
    # remove newlines, put everything in lowercase.
    return string.replace("\n", " ").lower()

def check(attempt_json: list[dict], ground_truth_json: list[dict]) -> pd.DataFrame:
    error_count = 0
    results = []

    print("\n" + "="*80)
    print(f"{'DOCUMENT ANALYSIS':^80}")
    print("="*80)

    for attempt_page, ground_truth_page in zip(attempt_json, ground_truth_json):
        doc_errors = []
        for field_name, field in FEMA_FORM_010_0_13.fields.items():
            obj = {
                # document metadata
                'uuid': attempt_page['uuid'],
                'original_filename': attempt_page['original_filename'],
                # field data
                'field_name': field_name,
                'attempt': attempt_page[field_name],
                'truth': ground_truth_page[field_name],
                # field metadata
                'is_checkbox': field.is_boolean,
                'is_multiselect': field.is_multi_select,
                'error_type': ''
            }
            correct = attempt_page[field_name] == ground_truth_page[field_name]
            if not field.is_boolean and not field.is_multi_select:
                correct = preprocess_strings(attempt_page[field_name]) == preprocess_strings(ground_truth_page[field_name])
            obj['correct'] = correct
            results.append(obj)
            if not correct:
                doc_errors.append(field_name)
                error_count += 1
                obj['error_type'] = classify_error(
                    attempt_page[field_name],
                    ground_truth_page[field_name],
                    field.is_boolean,
                    field.is_multi_select
                    )
        if doc_errors:
            print(f"\nDocument: {attempt_page['original_filename']}")
            print(f"Fields with errors: {', '.join(doc_errors)}")

    print(f"\nTotal errors found: {error_count}")

    results = pd.DataFrame(results)
    return results

def analyze(results: pd.DataFrame):
    total_fields = len(results)
    correct_fields = results['correct'].sum()
    overall_accuracy = correct_fields / total_fields
    
    print("\n" + "="*80)
    print(f"{'ANALYSIS SUMMARY':^80}")
    print("="*80)
    print(f"\nOverall Accuracy: {overall_accuracy:.2%} ({int(correct_fields)}/{total_fields} fields correct)")
    
    # Checkbox field analysis
    print("\n" + "-"*80)
    print(f"{'CHECKBOX FIELD ANALYSIS':^80}")
    print("-"*80)
    
    checkbox_accuracy = results.loc[results["is_checkbox"], "correct"].mean()
    checkbox_count = len(results[results["is_checkbox"]])
    print(f"Overall Checkbox Accuracy: {checkbox_accuracy:.2%} ({int(checkbox_accuracy * checkbox_count)}/{checkbox_count} fields)")

    print("\nAccuracy by Document:")
    checkbox_accuracies_by_doc = results[results['is_checkbox']].groupby(
            ['uuid', 'original_filename'])['correct'].mean()
    
    for (uuid, filename), accuracy in checkbox_accuracies_by_doc.items():
        print(f"  {filename:<40} {accuracy:.2%}")

    # Multi-select field analysis
    print("\n" + "-"*80)
    print(f"{'MULTI-SELECT FIELD ANALYSIS':^80}")
    print("-"*80)
    
    multiselect_accuracy = results.loc[results["is_multiselect"], "correct"].mean()
    multiselect_count = len(results[results["is_multiselect"]])
    print(f"Overall Multi-Select Accuracy: {multiselect_accuracy:.2%} ({int(multiselect_accuracy * multiselect_count)}/{multiselect_count} fields)")

    print("\nAccuracy by Document:")
    multiselect_accuracies_by_doc = results[results['is_multiselect']].groupby(
            ['uuid', 'original_filename'])['correct'].mean()
    
    for (uuid, filename), accuracy in multiselect_accuracies_by_doc.items():
        print(f"  {filename:<40} {accuracy:.2%}")

    # Field-level accuracy analysis
    print("\n" + "-"*80)
    print(f"{'FIELD-LEVEL ACCURACY ANALYSIS':^80}")
    print("-"*80)
    
    field_accuracies = results.groupby('field_name')['correct'].agg(['mean', 'count'])
    field_accuracies = field_accuracies[field_accuracies['mean'] < 1.0].sort_values('mean')
    
    if len(field_accuracies) > 0:
        print("\nFields with Errors (Worst to Best):")
        for field_name, row in field_accuracies.iterrows():
            print(f"  {field_name:<40} {row['mean']:.2%} ({int(row['mean'] * row['count'])}/{int(row['count'])} correct)")
    else:
        print("\nNo fields with errors detected!")

    # Error type analysis
    print("\n" + "-"*80)
    print(f"{'ERROR TYPE ANALYSIS':^80}")
    print("-"*80)
    
    if len(results[~results['correct']]) > 0:
        error_counts = results[~results['correct']]['error_type'].value_counts()
        total_errors = error_counts.sum()
        
        print(f"\nError Distribution ({total_errors} total errors):")
        for error_type, count in error_counts.items():
            percentage = 100 * count / total_errors
            print(f"  {error_type:<20} {count:>3} ({percentage:.1f}%)")
            
        # Give explanations for common error types
        print("\nError Type Explanations:")
        explanations = {
            "partial_match": "List fields where some but not all elements match",
            "checkbox_error": "Boolean fields with incorrect value",
            "substring_match": "Text fields where one is contained within the other",
            "content_mismatch": "Text fields with completely different content",
            "false_positive": "Empty field in ground truth but content in parsed result",
            "false_negative": "Content in ground truth but empty in parsed result",
            "case_mismatch": "Text differs only in capitalization",
            "format_error": "Expected data type mismatch",
            "type_mismatch": "Different data types between ground truth and parsed result",
            "complete_mismatch": "List fields with no common elements"
        }
        
        for error_type in error_counts.index:
            if error_type in explanations:
                print(f"  {error_type:<20}: {explanations[error_type]}")
    else:
        print("\nNo errors detected!")
        
    print("\n" + "="*80)

# def analyze(results: pd.DataFrame):
#     print('Checkbox Analysis ---')
#     print(f'Overall Accuracy: {results.loc[results["is_checkbox"], "correct"].mean():0.2f}')
#
#     checkbox_accuracies_by_doc = results[results['is_checkbox']].groupby(
#             ['uuid', 'original_filename'])['correct'].mean()
#
#     print(checkbox_accuracies_by_doc)
#
#     print('Multi-Select Analysis ---')
#     print(f'Overall Accuracy: {results.loc[results["is_multiselect"], "correct"].mean():0.2f}')
#
#     checkbox_accuracies_by_doc = results[results['is_multiselect']].groupby(
#             ['uuid', 'original_filename'])['correct'].mean()
#
#     print(checkbox_accuracies_by_doc)
#
#     # Analyze accuracy by field name
#     field_accuracies = results.groupby('field_name')['correct'].agg(['mean', 'count'])
#     field_accuracies = field_accuracies[field_accuracies['mean'] < 1.0].sort_values('mean')
#     print("\nField-Level Accuracy (Worst to Best):")
#     print(field_accuracies)
#
#     # After the field-level analysis section, add:
#     print("\nError Type Distribution:")
#     error_counts = results[~results['correct']]['error_type'].value_counts()
#     print(error_counts)
#
#     # Add percentage distribution 
#     error_percentages = 100 * error_counts / error_counts.sum()
#     print("\nError Type Distribution (%):")
#     for error_type, percentage in error_percentages.items():
#         print(f"{error_type}: {percentage:.1f}%")

def main():
    parser = argparse.ArgumentParser(description='Evaluate FEMA form parsing against ground truth.')
    parser.add_argument('parsed_file', help='Path to the JSON file with parsed form data')
    parser.add_argument('--ground-truth', default='test_set_truth.json', 
                        help='Path to the ground truth JSON file (default: test_set_truth.json)')
    
    args = parser.parse_args()
    
    try:
        ground_truth, attempt = load_data(args.ground_truth, args.parsed_file)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return 1
    
    results = check(attempt, ground_truth)
    analyze(results)

    return 0

if __name__ == "__main__":
    exit(main())
