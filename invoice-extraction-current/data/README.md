# Data Directory

This directory contains input data, temporary files, and ground truth for evaluation.

## Structure

```
data/
├── input/          # Place invoice files here (PDF, JPG, PNG)
├── temp/           # Temporary processing files (auto-cleaned)
└── ground_truth.json  # Evaluation ground truth data
```

## Notes

- Input files will be processed and moved/copied as needed
- Temporary files are automatically cleaned after processing
- Ground truth format is documented in the evaluation guide
