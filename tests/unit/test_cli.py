from agentbench.cli import create_parser


def test_cli_parser_subcommands():
    parser = create_parser()

    # list
    args = parser.parse_args(["list"])
    assert args.command == "list"

    # validate
    args = parser.parse_args(["validate", "config-recovery-001"])
    assert args.command == "validate"
    assert args.task_id == "config-recovery-001"

    # run
    args = parser.parse_args(
        ["run", "config-recovery-001", "--agent", "scripted", "--docker"]
    )
    assert args.command == "run"
    assert args.agent == "scripted"
    assert args.docker is True

    # eval
    args = parser.parse_args(
        ["eval", "config-recovery-001", "--trials", "5", "-k", "1,3"]
    )
    assert args.command == "eval"
    assert args.trials == 5
    assert args.k == "1,3"

    # leaderboard
    args = parser.parse_args(["leaderboard", "--output-html", "test.html"])
    assert args.command == "leaderboard"
    assert args.output_html == "test.html"

    # scaffold
    args = parser.parse_args(["scaffold", "new-task-001", "--difficulty", "hard"])
    assert args.command == "scaffold"
    assert args.task_id == "new-task-001"
    assert args.difficulty == "hard"


def test_cli_list_command(capsys):
    parser = create_parser()
    args = parser.parse_args(["list"])
    exit_code = args.func(args)
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "config-recovery-001" in captured.out


def test_cli_validate_command(capsys):
    parser = create_parser()
    args = parser.parse_args(["validate", "config-recovery-001"])
    exit_code = args.func(args)
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "passed all integrity validations" in captured.out


def test_cli_leaderboard_command(capsys, tmp_path):
    parser = create_parser()
    html_out = tmp_path / "leaderboard.html"
    md_out = tmp_path / "LEADERBOARD.md"
    args = parser.parse_args(
        ["leaderboard", "--output-html", str(html_out), "--output-md", str(md_out)]
    )
    exit_code = args.func(args)
    assert exit_code == 0
    assert html_out.is_file()
    assert md_out.is_file()


def test_cli_scaffold_command(capsys, tmp_path):
    parser = create_parser()
    benchmarks_tmp = tmp_path / "benchmarks"
    args = parser.parse_args(
        [
            "--benchmarks-dir",
            str(benchmarks_tmp),
            "scaffold",
            "temp-cli-task",
            "--name",
            "Temp CLI Task",
        ]
    )
    exit_code = args.func(args)
    assert exit_code == 0
    assert (benchmarks_tmp / "temp-cli-task" / "task.yaml").is_file()
