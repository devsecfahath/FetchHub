# Contributing to MediaFetch Bot

Thank you for considering contributing! Here is everything you need to know.

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/media-downloader-bot.git
   cd media-downloader-bot
   ```
3. **Install** dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. **Set up** your `.env` file:
   ```bash
   cp .env.example .env
   # Fill in your BOT_TOKEN and ADMIN_IDS
   ```

## Making Changes

- Create a new branch for your feature or bugfix:
  ```bash
  git checkout -b feature/your-feature-name
  ```
- Make your changes, keeping the modular structure in mind.
- Run the test suite to make sure nothing is broken:
  ```bash
  python -m unittest discover tests
  ```

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR.
- Write a clear PR description explaining what you changed and why.
- Make sure all tests pass before submitting.
- If you add a new feature, add a test for it in `tests/`.

## Reporting Issues

- Use GitHub Issues to report bugs or request features.
- Include the error message, your Python version, and steps to reproduce.

## Code Style

- Follow existing code conventions (async-first, type hints where possible).
- Use descriptive variable and function names.
- Comment non-obvious logic.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
