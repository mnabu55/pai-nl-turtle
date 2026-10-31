from setuptools import setup

package_name = "nl_turtle"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="pai-final",
    maintainer_email="noreply@example.com",
    description="Drive turtlesim from a list of motion steps.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "square_demo = nl_turtle.square_demo:main",
            "nl_commander = nl_turtle.nl_commander:main",
        ],
    },
)
