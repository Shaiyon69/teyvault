# Entry point for `flet build` (Android / iOS) and `flet pack` (Windows installer).
import sys

if "--weblogin" in sys.argv:  # the installed exe re-launched by weblogin.sign_in()
    from teyvat.weblogin import _main
    _main()
elif "--daily" in sys.argv:  # the hourly Task Scheduler run (background.task_command)
    from teyvat.cli import main
    main(["daily", "--notify"])
else:
    from teyvat.gui import run
    run()
