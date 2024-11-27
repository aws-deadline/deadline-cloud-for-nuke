## 0.18.8 (2024-11-27)

### Bug Fixes
* Revert &#34;fix: Resolve menu.py not found error when installing via pip (#172)&#34; (#175)([`3d3a8e9`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/3d3a8e9b3acc77988c0967744d8031ebb12509c1))



## 0.18.7 (2024-11-21)



### Bug Fixes
* Resolve menu.py not found error when installing via pip (#172) ([`9364964`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/9364964e50b02cda097df3866fa6c7bc755d7878))

## 0.18.6 (2024-10-21)



### Bug Fixes
* Revert &#34;fix: Resolve menu.py not found error when running pip install deadline-cloud-for-nuke -t &lt;folder&gt; (#165)&#34; (#170) ([`71b8c8b`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/71b8c8b762f7f3a1999640a4e6a3d646e575146d))

## 0.18.5 (2024-10-16)


### Features
* Handle different OCIO configs in adapter (#168) ([`5d55675`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/5d55675eab8e17155eb7a5044f9453b473700fb4))
* Added support for including gizmos in job bundle (#162) ([`a0704a3`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/a0704a359d4e83daade6bf41b1b766886384c37d))

### Bug Fixes
* Add OCIO configuration to Job Environments (#166) ([`0eb87cb`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/0eb87cbdb1bf86dff2799b48ba4ef89c70341c21))
* Resolve menu.py not found error when running pip install deadline-cloud-for-nuke -t &lt;folder&gt; (#165) ([`82b7eb2`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/82b7eb2d9f509a09c9974ec237a1031f4782847a))
* Update frame range when write node is selected (#161) ([`e6398c9`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/e6398c919ae7faa099f007ad2195732958ac0f9a))

## 0.18.4 (2024-08-12)



### Bug Fixes
* Update write nodes and views when refeshing the job settings ui (#151) ([`1175cc9`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/1175cc9c4d71bbaeec49d707f40058feb6dba4f9))

## 0.18.3 (2024-05-29)


### Features
* add ability to configure timeouts in submission UI (#143) ([`4535fa0`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/4535fa0a9bbd9a05ca1dd204da70e02f62b7c033))

### Bug Fixes
* include adaptor wheels developer option (#142) ([`0edc735`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/0edc735b2a2f117abddb43d9fc5cfdd013c315f1))

## 0.18.2 (2024-05-01)



### Bug Fixes
* check for movie output regardless of adaptor override (#134) ([`0fda9a7`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/0fda9a75338fa30bbe4125bab503b8a6654e7d4f))

## 0.18.1 (2024-04-02)



### Bug Fixes
* show the correct supported versions (#129) ([`d2e5774`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/d2e577419269cce3d3c5c3db19423682e57a36bc))

## 0.18.0 (2024-04-01)

### BREAKING CHANGES
* public release (#123) ([`515891b`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/515891bec7f82da0e8efaab2e6f94adf1a7289b7))


### Bug Fixes
* include deps with openjd adaptor package (#121) ([`fed5129`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/fed5129a936522b26bc34d955b03f4d6ccf1387a))
* include the adaptor deps in the package (#119) ([`ca51be5`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/ca51be5de62d5de1e5c851ce769473be3dacd17b))
* incorrect package name in create adaptor script (#120) ([`ba2f9f8`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/ba2f9f8a37839c382bb19dfadfb548028022c578))
* set python 3.8 to minimum python version in hatch testing matrix (#123) ([`515891b`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/515891bec7f82da0e8efaab2e6f94adf1a7289b7))

## 0.17.2 (2024-03-26)


### Features
* Improve telemetry for submitter and adaptor (#103) ([`0811e05`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/0811e0500547326ef9b3d369f1aa3211073c5616))

### Bug Fixes
* include deadline-cloud in the adaptor packaging script (#117) ([`9a72baf`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/9a72baff204d2073c35fdede2dc238c2e6515ee0))

## 0.17.1 (2024-03-15)

### Chore
* update deps deadline-cloud 0.40 (#107) ([`6503f29`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/6503f293c9f9ea7be5a513d84dffd4d4f0c2dc5f))


## 0.17.0 (2024-03-08)

### BREAKING CHANGES
* **deps**: update openjd-adaptor-runtime to 0.5 (#100) ([`b01e7f5`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/b01e7f5a2bdcc0b18a39d63737067143b5a126e2))



## 0.16.0 (2024-02-21)

### BREAKING CHANGES
* Create a script to build adaptor package artifacts (#85) ([`0039d36`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/0039d3607caa0a441d8f12cd3dd5687f26fb1c02))


### Bug Fixes
* include description on submission (#89) ([`13b4a56`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/13b4a56a263d55ef1277711bca8e9a01db78a83a))
* prevent menu clash with Deadline10 (#86) ([`d5f3d12`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/d5f3d128b1eed20997959aef6b5f5cb5c9fb0f42))
* use right mode when opening toml file (#83) ([`7097cf3`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/7097cf37ff71ee23bb054348d7a4967c17255c5f))
* libtoml -&gt; tomllib in depsBundle.py (#82) ([`70b3eaf`](https://github.com/aws-deadline/deadline-cloud-for-nuke/commit/70b3eafff63722232d9568ff4d8ad1f6b3a7f58f))

