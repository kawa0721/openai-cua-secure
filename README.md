# Computer Using Agent Sample App (Secure Version)

Get started building a [Computer Using Agent (CUA)](https://platform.openai.com/docs/guides/tools-computer-use) with the OpenAI API.

> [!CAUTION]  
> Computer use is in preview. Because the model is still in preview and may be susceptible to exploits and inadvertent mistakes, we discourage trusting it in authenticated environments or for high-stakes tasks.

## Security Note

This is a secured fork of the original openai-cua-custom project. The main difference is that API keys are now loaded from environment variables, rather than being hardcoded in the source code.

## Set Up & Run

1. Create a `.env` file based on the `.env.example` template:

```shell
cp .env.example .env
```

2. Edit the `.env` file with your actual API keys:

```
OPENAI_API_KEY=your_actual_openai_api_key
OPENAI_ORG=your_org_id_if_applicable
```

3. Set up python env and install dependencies:

```shell
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4. Run CLI to let CUA use a local browser window, using [playwright](https://playwright.dev/). (Stop with CTRL+C)

```shell
python cli.py --computer local-playwright
```

> [!NOTE]  
> The first time you run this, if you haven't used Playwright before, you will be prompted to install dependencies. Execute the command suggested, which will depend on your OS.

Other included sample [computer environments](#computer-environments):

- [Docker](https://docker.com/) (containerized desktop)
- [Browserbase](https://www.browserbase.com/) (remote browser, requires account)
- [Scrapybara](https://scrapybara.com) (remote browser or computer, requires account)
- ...or implement your own `Computer`!

## Overview

The computer use tool and model are available via the [Responses API](https://platform.openai.com/docs/api-reference/responses). At a high level, CUA will look at a screenshot of the computer interface and recommend actions. Specifically, it sends `computer_call`(s) with `actions` like `click(x,y)` or `type(text)` that you have to execute on your environment, and then expects screenshots of the outcomes.

You can learn more about this tool in the [Computer use guide](https://platform.openai.com/docs/guides/tools-computer-use).

## Abstractions

This repository defines two lightweight abstractions to make interacting with CUA agents more ergonomic. Everything works without them, but they provide a convenient separation of concerns.

| Abstraction | File                    | Description                                                                                                                                                                                                  |
| ----------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `Computer`  | `computers/computer.py` | Defines a `Computer` interface for various environments (local desktop, remote browser, etc.). An implementation of `Computer` is responsible for executing any `computer_action` sent by CUA (clicks, etc). |
| `Agent`     | `agent/agent.py`        | Simple, familiar agent loop – implements `run_full_turn()`, which just keeps calling the model until all computer actions and function calls are handled.                                                    |

## CLI Usage

The CLI (`cli.py`) is the easiest way to get started with CUA. It accepts the following arguments:

- `--computer`: The computer environment to use. See the [Computer Environments](#computer-environments) section below for options. By default, the CLI will use the `local-playwright` environment.
- `--input`: The initial input to the agent (optional: the CLI will prompt you for input if not provided)
- `--debug`: Enable debug mode with detailed logging (equivalent to `--log-level DEBUG`).
- `--show`: Show images (screenshots) during the execution (equivalent to `--screenshot all`).
- `--start-url`: Start the browsing session with a specific URL (only for browser environments). By default, the CLI will start the browsing session with `https://bing.com`.

### Unified Parameter System

The CLI now includes a unified parameter system that controls three key aspects of the application:

- **Browser Visibility**: Control whether the browser window is visible or runs in headless mode
- **Logging Level**: Control the verbosity of logging output
- **Screenshot Control**: Control when screenshots are captured

#### Browser and Logging Parameters

- `--headless`: Run in headless mode without showing browser window. When enabled, the browser will run in the background.
- `--log-level`: Set logging verbosity level. Options include:
  - `NONE`: No logging output
  - `ERROR`: Only error messages
  - `INFO`: Basic informational messages (default)
  - `ACTION`: Browser actions only
  - `DEBUG`: Detailed debug information
  - `ALL`: All possible logging
- `--quiet`: Disable all logging (equivalent to `--log-level NONE`)
- `--screenshot`: Control when screenshots are taken. Options include:
  - `none`: No screenshots are taken
  - `search`: Only take screenshots during search operations
  - `all`: Take screenshots for all operations (default)

#### Search Engine Parameters

The application now supports customizing search parameters with resilient fallback between search engines:

- `--resilient-search`: Enable resilient search with engine fallback
- `--search-engine`: Preferred search engine (`auto`, `google`, `bing`, `duckduckgo`, `yahoo`)
- `--humanlike-search`: Enable human-like behavior during search to avoid detection
- `--search-language`: Language code for search results (e.g., `en`, `ja`, `fr`)
- `--search-region`: Country/region code for search results (e.g., `us`, `jp`, `fr`)
- `--search-safe`: Enable safe search filtering
- `--search-time`: Time period for search results (`day`, `week`, `month`, `year`)
- `--search-type`: Content type to search for (`all`, `news`, `images`, `videos`, `shopping`)
- `--search-site`: Limit search to a specific site (e.g., `example.com`)
- `--search-results`: Number of search results to request (usually 10-100)

#### Example Usage

```shell
# Run with headless browser, action-level logging, and search-only screenshots
python cli.py --headless --log-level ACTION --screenshot search

# Run with visible browser but no logging
python cli.py --quiet

# Run fully headless with minimal output
python cli.py --headless --log-level ERROR --screenshot none

# Run with debug logging and all screenshots
python cli.py --log-level DEBUG --screenshot all

# Run with resilient search in Japanese language, limited to Japan region
python cli.py --resilient-search --search-language ja --search-region jp

# Run with Bing search engine, safe search enabled, limited to news content
python cli.py --resilient-search --search-engine bing --search-safe --search-type news

# Search for weather in Japanese language and region
python cli.py --resilient-search --search-language ja --search-region jp --input "東京の天気は？"
```

#### Example Scripts

For complete examples demonstrating various features:

```shell
# Headless browser and screenshot control
python -m examples.headless_screenshot_example --headless --log-level ACTION --screenshot search

# Resilient search with parameters
python -m examples.search_params_example "Tokyo weather" --language ja --country jp --show

# Weather search with language settings
python -m examples.weather_example --language ja --show
```

### Run examples (optional)

The `examples` folder contains more examples of how to use CUA.

```shell
python -m examples.weather_example
```

For reference, the file `simple_cua_loop.py` implements the basics of the CUA loop.

You can run it with:

```shell
python simple_cua_loop.py
```

## Computer Environments

CUA can work with any `Computer` environment that can handle the [CUA actions](https://platform.openai.com/docs/api-reference/responses/object#responses/object-output):

| Action                             | Example                         |
| ---------------------------------- | ------------------------------- |
| `click(x, y, button="left")`       | `click(24, 150)`                |
| `double_click(x, y)`               | `double_click(24, 150)`         |
| `scroll(x, y, scroll_x, scroll_y)` | `scroll(24, 150, 0, -100)`      |
| `type(text)`                       | `type("Hello, World!")`         |
| `wait(ms=1000)`                    | `wait(2000)`                    |
| `move(x, y)`                       | `move(24, 150)`                 |
| `keypress(keys)`                   | `keypress(["CTRL", "C"])`       |
| `drag(path)`                       | `drag([[24, 150], [100, 200]])` |

This sample app provides a set of implemented `Computer` examples, but feel free to add your own!

| Computer            | Option             | Type      | Description                       | Requirements                                                     |
| ------------------- | ------------------ | --------- | --------------------------------- | ---------------------------------------------------------------- |
| `LocalPlaywright`   | local-playwright   | `browser` | Local browser window              | [Playwright SDK](https://playwright.dev/)                        |
| `Docker`            | docker             | `linux`   | Docker container environment      | [Docker](https://docs.docker.com/engine/install/) running        |
| `Browserbase`       | browserbase        | `browser` | Remote browser environment        | [Browserbase](https://www.browserbase.com/) API key in `.env`    |
| `ScrapybaraBrowser` | scrapybara-browser | `browser` | Remote browser environment        | [Scrapybara](https://scrapybara.com/dashboard) API key in `.env` |
| `ScrapybaraUbuntu`  | scrapybara-ubuntu  | `linux`   | Remote Ubuntu desktop environment | [Scrapybara](https://scrapybara.com/dashboard) API key in `.env` |

Using the CLI, you can run the sample app with different computer environments using the options listed above:

```shell
python cli.py --show --computer <computer-option>
```

For example, to run the sample app with the `Docker` computer environment, you can run:

```shell
python cli.py --show --computer docker
```

### Docker Setup

If you want to run the sample app with the `Docker` computer environment, you need to build and run a local Docker container.

Open a new shell to build and run the Docker image. The first time you do this, it may take a few minutes, but subsequent runs should be much faster. Once the logs stop, proceed to the next setup step. To stop the container, press CTRL+C on the terminal where you ran the command below.

```shell
docker build -t cua-sample-app .
docker run --rm -it --name cua-sample-app -p 5900:5900 --dns=1.1.1.3 -e DISPLAY=:99 cua-sample-app
```

> [!NOTE]  
> We use `--dns=1.1.1.3` to restrict accessible websites to a smaller, safer set. We highly recommend you take similar safety precautions.

> [!WARNING]  
> If you get the below error, then you need to kill that container.
>
> ```
> docker: Error response from daemon: Conflict. The container name "/cua-sample-app" is already in use by container "e72fcb962b548e06a9dcdf6a99bc4b49642df2265440da7544330eb420b51d87"
> ```
>
> Kill that container and try again.
>
> ```shell
> docker rm -f cua-sample-app
> ```

### Hosted environment setup

This repository contains example implementations of third-party hosted environments.
To use these, you will need to set up an account with the service by following the links above and add your API key to the `.env` file:

```
# For Browserbase
BROWSERBASE_API_KEY=your_browserbase_api_key

# For Scrapybara
SCRAPYBARA_API_KEY=your_scrapybara_api_key
```

## Function Calling

The `Agent` class accepts regular function schemas in `tools` – it will return a hard-coded value for any invocations.

However, if you pass in any `tools` that are also defined in your `Computer` methods, in addition to the required `Computer` methods, they will be routed to your `Computer` to be handled when called. **This is useful for cases where screenshots often don't capture the search bar or back arrow, so CUA may get stuck. So instead, you can provide a `back()` or `goto(url)` functions.** See `examples/playwright_with_custom_functions.py` for an example.

## Security Best Practices

This repository follows security best practices:

1. **Environment Variables**: API keys and sensitive information are stored in `.env` files, which are excluded from version control by `.gitignore`.
2. **Template Files**: `.env.example` provides a template for required environment variables without actual credentials.
3. **Code Review**: Regular code reviews and security scans help identify potential vulnerabilities.

## Risks & Safety considerations

This repository provides example implementations with basic safety measures in place.

We recommend reviewing the best practices outlined in our [guide](https://platform.openai.com/docs/guides/tools-computer-use#risks-and-safety), and making sure you understand the risks involved with using this tool.
