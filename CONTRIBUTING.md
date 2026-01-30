# Contributing Guidelines

Thank you for your interest in contributing to the **TropicalALAN_Lab_PTY Remote-sensing System**. Contributions of all types (code, tests, documentation, bug reports, ideas) are welcome and appreciated.

## Quick Start

1. **Read the documentation**:
   - [Main README](./README.md) for project overview, setup, and APIs
   - [Module READMEs](./scripts/) for technical details
   - [System architecture diagram](./docs/system_architecture.puml) for a simplified view of the system

2. **Find an issue to work on**:
   - Browse GitHub Issues for labels: `good first issue`, `help wanted`, `bug`, `enhancement`
   - Don't see what you want to work on? Open an issue first to discuss

3. **Set up your environment**:
   ```bash
   git clone [repository-url]
   cd Remote-sensing
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   npm install
   ```

---

## Reporting Issues

### Bug Reports

Please search for existing issues before creating a new one.

**Include**:
- **Title**: Clear, concise description of the bug
- **Environment**: OS, Python version, system type
- **Steps to reproduce**: Exact steps to trigger the bug
- **Expected vs actual behavior**: What should happen vs what does happen
- **Error logs**: Full traceback or relevant log output from `logs/`
- **Screenshots**: Visual evidence if applicable
- **Data source**: ISS / NOAA VIIRS / DMSP-OLS and whether Google Earth Engine is involved

**Example**:
```
Title: ISS API download fails with timeout error

Environment:
- OS: Ubuntu 24.04
- Python: 3.10.12
- System: Windows 11 + WSL2 (Ubuntu 24.04)

Steps to reproduce:
1. Run: python scripts/backend/nasa_api_client.py --limit 100
2. Wait for API calls to start
3. After ~5 minutes, download fails

Expected: All 100 images download successfully
Actual: Process terminates with timeout error after ~200 images

Logs: [paste relevant section from logs/iss/]
```

### Enhancement Requests

**Include**:
- **Description**: What feature or improvement you want
- **Motivation**: Why this would be valuable
- **Suggested approach**: Optional technical thoughts
- **Example use case**: How would you use this feature

---

## Contributing Code

### Branch Naming

Use descriptive branch names:
- `fix/issue-description` - Bug fixes
- `feature/feature-name` - New features
- `docs/update-section` - Documentation updates
- `refactor/module-name` - Code refactoring
- `test/feature-name` - Test additions

Example:
```bash
git checkout -b fix/viirs-cloud-masking-issue
git checkout -b feature/batch-image-processing
git checkout -b docs/scientific-methodology
```

### Commit Messages

Follow this format:

```
[Type] Brief summary (50 chars max)

Longer description explaining what changed and why.
Wrap at 72 characters. Include issue references like:
- Closes #123
- Related to #456
- Fixes issue with handling edge cases

Technical details:
- Changed X function to improve performance
- Added validation for Y parameter
- Updated dependencies in requirements.txt
```

**Types**:
- `[fix]` - Bug fix
- `[feat]` - New feature
- `[docs]` - Documentation
- `[refactor]` - Code restructuring (no functionality change)
- `[test]` - Test additions/updates
- `[perf]` - Performance improvements
- `[chore]` - Build, dependencies, etc.

**Examples**:
```bash
git commit -m "[fix] Correct VIIRS cloud masking threshold

Previously used hardcoded value of 0.5. Now reads from configuration.
Improves accuracy by ~8% on validation dataset.
Closes #42"

git commit -m "[feat] Add parallel image processing

Implements ThreadPoolExecutor for batch processing.
--parallel flag allows custom worker count.
See scripts/backend/README.md for usage."
```

### Pull Requests

1. **Before submitting**:
   ```bash
   # Check code style
   black scripts/ db/ map/ --check
   isort scripts/ db/ map/ --check
   ruff check scripts/ db/ map/
   ```

2. **PR title and description**:
   - Title: `[Type] Brief description`
   - Description: Explain what changed and why
   - Link related issues: `Closes #123`

3. **PR checklist** (include in description):
   ```markdown
   - [ ] I've read README.md and CONTRIBUTING.md
   - [ ] Code follows the project style (black, isort, ruff)
   - [ ] Commit messages are descriptive
   - [ ] Changes are verified locally (manual checks)
   - [ ] Documentation is updated if needed
   - [ ] No breaking changes to existing APIs
   ```

---

## Code Style & Linting

### Python Code

**Requirements**: Python 3.8+ (3.10.12 recommended)

**Format and lint**:
```bash
# Install tools
pip install black isort ruff

# Format code
black scripts/ db/ map/
isort scripts/ db/ map/

# Check for issues
ruff check scripts/ db/ map/
```

**Style guidelines**:
- Use 4-space indentation
- Line length: 88 characters (black default)
- Use type hints where practical
- Document complex functions with docstrings
- Follow PEP 8 conventions

**Example**:
```python
def collect_image_metadata(
   image_path: str,
   output_dir: str,
) -> Dict[str, Any]:
   """
   Collect metadata from a downloaded image.

   Args:
      image_path: Path to the image file
      output_dir: Directory for output metadata files

   Returns:
      Dictionary with collected metadata

   Raises:
      FileNotFoundError: If image file doesn't exist
      ValueError: If metadata extraction fails
   """
   # Implementation
   pass
```

### JavaScript/Node.js Code

**Requirements**: Node.js 16+ LTS

**Format and lint**:
```bash
# Install tools
npm install --save-dev prettier eslint

# Format code
npx prettier --write scripts/periodic_tasks/*.js

# Check for issues
npx eslint scripts/periodic_tasks/
```

**Style**:
- 2-space indentation
- Use `const`/`let` (no `var`)
- Use arrow functions where appropriate
- Add JSDoc comments for public functions

### Shell Scripts

**Requirements**: POSIX-compatible or bash

**Checks**:
```bash
# Check syntax
bash -n scripts/launch_noaa.sh

# Use shellcheck for common issues
shellcheck scripts/launch_noaa.sh
```

**Guidelines**:
- Use `set -euo pipefail` for safety
- Quote variables: `"$var"` not `$var`
- Use `[[ ]]` instead of `[ ]`
- Document complex logic with comments

---

## Documentation Contributions

Good documentation is just as important as code!

### Where to Contribute

1. **README files**: Main [README](./README.md), module READMEs
2. **API documentation**: In-code docstrings and module READMEs
3. **System diagrams**: [docs/system_architecture.puml](./docs/system_architecture.puml)
4. **Visual guides**: [`docs/VISUAL_GUIDE.md`](./docs/VISUAL_GUIDE.md)
5. **Inline comments**: Explain "why" not "what"

### Documentation Style

- Use clear, active language
- Include examples and code snippets
- Provide external links to references
- Update screenshots if UI changes
- Test examples before submitting

---

## Development Workflow

### Local Development

1. **Create feature branch**:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make changes and commit**:
   ```bash
   git add scripts/backend/my_file.py
   git commit -m "[feat] Add new processing function"
   ```

3. **Verify locally**:
   ```bash
   black scripts/
   ruff check scripts/
   ```

4. **Push and create PR**:
   ```bash
   git push origin feature/my-new-feature
   # Then open PR on GitHub
   ```

### Common Development Tasks

**Add a new data source**:
1. Create new module in `scripts/new_source/`
2. Implement API client class
3. Add to `scripts/periodic_tasks/tasks.json`
4. Create README in module directory
5. Update main `README.md` with reference
6. Update [docs/system_architecture.puml](./docs/system_architecture.puml) if it affects architecture

**Fix a bug in VIIRS processing**:
1. Create issue describing the bug
2. Branch: `git checkout -b fix/viirs-bug-description`
3. Make changes to `scripts/noaa/`
4. Test with sample data
5. Submit PR with before/after results

**Improve documentation**:
1. Identify unclear section
2. Improve clarity, add examples
3. Update related files (check cross-references)
4. Submit PR with explanation

**Update API credentials guidance**:
1. Review the "Required APIs & Credentials Setup" section in [README](./README.md)
2. Confirm any changes with official sources (NASA ISS Photo Database and Google Earth Engine)
3. Update the README and module docs accordingly

---

## Continuous Integration

The repository uses automated checks:

- **Code formatting**: black, isort
- **Linting**: ruff for Python

Ensure your PR passes all checks before requesting review.

---

## Code Review Process

1. **Maintainers review** your PR for:
   - Code quality and style
   - Alignment with project goals
   - Documentation completeness
   - Manual validation notes (when applicable)
   - Potential issues

2. **Feedback**:
   - Constructive comments are about code, not person
   - Ask questions if something is unclear
   - Be open to suggestions

3. **Approval and merge**:
   - At least one maintainer approval required
   - All CI checks must pass
   - Branch is squashed and merged

---

## Community Standards

### Be Respectful

- Assume good intent
- Be inclusive and welcoming
- Respect different perspectives
- No harassment or discrimination

### Be Constructive

- Give specific feedback with examples
- Suggest improvements, not just criticisms
- Help others learn and grow

---

## Contact & Questions

**General questions**: Open a GitHub Discussion or issue

**Technical/Scientific guidance**:
- Dr. Jose Robles: `jrobles@indicatic.org.pa` (research direction)
- Jose Jaen: `jose.jaenj08@hotmail.com` (code & implementation)
- Alexandre Olivie: `alexandre.olivie@bordeaux-inp.fr` (technical details)

**Contribution ideas**:
- Bug fixes (see issues labeled `bug`)
- Performance improvements (see `perf`)
- Documentation (see `docs`, `good first issue`)
- New features (see `enhancement`)

---

## Resources

- [Python 3.10 Documentation](https://docs.python.org/3.10/)
- [Git Guide](https://git-scm.com/doc)
- [Black Code Formatter](https://black.readthedocs.io/)
- [Pytest Documentation](https://docs.pytest.org/)
- [GitHub Pull Requests Guide](https://docs.github.com/en/pull-requests)

---

## Contributor Recognition

Thank you for contributing! All contributors will be recognized in:
- Project README
- Release notes
- GitHub contribution graph

---

**Last Updated**: January 26, 2026  
**Version**: 2.0 (Updated for Remote-sensing project)

---

Thank you for making this project better!
