"""User-facing help, errors, and warnings.

``text(key, language, **values)`` returns the ``en`` or ``zh`` string.
``en`` is the default. ``zh`` is the previous Chinese wording.
"""
from __future__ import annotations


_CATALOG = {
    "description": {
        "en": "Read an ADMIXTURE Q matrix, order people by the rules you set, align columns across K, and write a structure bar plot.",
        "zh": "读 ADMIXTURE 的 Q，按指定规则排人，跨 K 对齐列，写出结构条形图。",
    },
    "epilog": {
        "en": (
            "Order: --order-file uses the list you give; otherwise groups are blocked in the --blocks order, and --within orders people inside each group.\n"
            "Inside a group, iid sorts by name, q sorts the column with the highest share in that group from high to low, hclust uses average linkage and distance 1-Pearson, and input keeps the original order in the Q file.\n"
            "With more than one K, greedy is the default align method. The match is Pearson greedy alignment, and the new column is placed at the top. --no-align keeps each Q file's own column order; if --anchor-group is also set, every K still places that group's purest person's main column at C1."
        ),
        "zh": (
            "排序：--order-file 用你给的名单；否则按 --blocks 的组序分块，组内用 --within。\n"
            "组内 iid=名字，q=该组占比最高的那一列从高到低，hclust=平均连锁、距离 1\u2212Pearson，input=Q 里的原顺序。\n"
            "多个 K 默认做 Pearson 贪心对齐，新列放在最上面。--no-align 保持每个 Q 自己的列顺序；若同时给了 --anchor-group，每个 K 仍把该组最纯的人的主列放到 C1。"
        ),
    },
    "help_q": {
        "en": "One or more matrix files, a quoted wildcard, or a directory. The default reads .Q and .q. Which extensions a directory reads is set by --q-format. File contents are whitespace-separated numbers.",
        "zh": "一个或多个矩阵文件，或带引号的通配符，或一个目录。默认读取 .Q 和 .q。目录里读哪些扩展名由 --q-format 决定。文件内容是空白分隔的数字。",
    },
    "help_q_format": {
        "en": "Matrix layout to read",
        "zh": "指定读取的矩阵排版",
    },
    "help_fam": {
        "en": "PLINK .fam, IID in column 2, row order matches Q",
        "zh": "PLINK .fam，IID 在第 2 列，行序与 Q 相同",
    },
    "help_ids": {
        "en": "One IID per line, row order matches Q. Keep only one of --fam, --ids, and --ind. Extra fields keep only the first token, and a warning is written to stderr",
        "zh": "一行一个 IID，行序与 Q 相同。与 --fam、--ind 只能留一个。多出来的字段只保留第一个，并在 stderr 警告",
    },
    "help_ind": {
        "en": "EIGENSTRAT .ind, three columns, sample id in column 1",
        "zh": "EIGENSTRAT 的 .ind，三列，样本号在第 1 列",
    },
    "help_groups": {
        "en": "Group table, tsv or csv, with a header",
        "zh": "分组表，tsv 或 csv，要有表头",
    },
    "help_blocks": {
        "en": "Left-to-right group order, comma-separated. A group name cannot contain a comma, or it will be split. Groups that are not listed are appended by name",
        "zh": "组的从左到右顺序，逗号分隔。组名不能含逗号，否则会被拆开。没写到的组按名字接在后面",
    },
    "help_rest_name": {
        "en": "Name used for a person whose group is empty. Default NA",
        "zh": "分组为空的人用这个名字。默认 NA",
    },
    "help_within": {
        "en": "How to order people inside each group. Default iid",
        "zh": "每一组内部怎么排。默认 iid",
    },
    "help_within_group": {
        "en": "Set one group, for example NA=hclust. Repeatable",
        "zh": "单独改某一组，例如 NA=hclust。可重复",
    },
    "help_order_file": {
        "en": "One IID per line. That list is the left-to-right order. When this is set, --blocks is not used",
        "zh": "一行一个 IID，这就是从左到右的顺序。给了它就不再用 --blocks",
    },
    "help_sort_k": {
        "en": "Which K to use when sorting by ancestry share. Default is the largest K",
        "zh": "按组分排序时用哪个 K。默认最大的 K",
    },
    "help_sort_col": {
        "en": "Every q-sorted group uses this column (counted from 1). If omitted, each group uses the column where its share is highest",
        "zh": "所有按 q 排序的组都用这一列（从 1 数）。不给就每组用自己占比最高的列",
    },
    "help_hclust_k": {
        "en": "Which K hclust uses. Default matches --sort-k",
        "zh": "hclust 用哪个 K。默认与 --sort-k 相同",
    },
    "help_hclust_dist": {
        "en": "hclust distance. Default correlation (1-Pearson)",
        "zh": "hclust 距离。默认 correlation（1\u2212Pearson）",
    },
    "help_hclust_linkage": {
        "en": "hclust linkage. Default average. ward requires euclidean",
        "zh": "hclust 连锁法。默认 average。ward 只能配 euclidean",
    },
    "help_hclust_pre": {
        "en": "dominant first splits each group by each person's highest column (order C1, C2, ...), then runs hclust inside each block. Default none",
        "zh": "dominant=组内先按每人最高的列分小块（C1、C2\u2026顺序），块内再 hclust。默认 none",
    },
    "help_hclust_olo": {
        "en": "Order leaves with scipy optimal_leaf_ordering",
        "zh": "叶序用 scipy optimal_leaf_ordering",
    },
    "help_align_mode": {
        "en": "all: everyone in the mask is used for alignment, and greedy, hungarian, pong, jaccard, clumpp-full, clumpp-greedy, and clumpp-largek use the same people. Pearson is used only for greedy and hungarian. core: keep only people whose qmax is strictly greater than --qmax at both adjacent K; if a group has nobody above that cut, keep that group's purest person at the lower K",
        "zh": "all=掩码内所有人参与对齐，greedy、hungarian、pong、jaccard、clumpp-full、clumpp-greedy、clumpp-largek 用同一批人。Pearson 只用于 greedy 和 hungarian。core=只留相邻两个 K 的 qmax 都严格大于 --qmax 的人；某一组没有人超过时，留下该组在较低 K 上最纯的一个人",
    },
    "help_align_method": {
        "en": "greedy takes the unused column with the highest Pearson value, one old column at a time (default). hungarian is the one-to-one match with the largest sum of Pearson values. pong allows one column from the previous K to split into two (Behr 2016); column 3 of align.tsv is the pong similarity and an extra split_parent column is written. jaccard matches one-to-one on sets of people; see --jaccard-set. clumpp-full pads the previous Q with one zero column and searches every permutation of the next Q to maximize G', keeping the lexicographically smallest permutation on a tie, and stops when K+1 is above 8. clumpp-greedy returns the same permutation as clumpp-full on one K to K+1 pair; the published Greedy differs only with more than two runs at one K. clumpp-largek pads the previous Q with one zero column and repeatedly locks the highest remaining column pair by column G', breaking ties by the smaller new-column index and then the smaller old-column index.",
        "zh": "greedy=按列顺序逐列取 Pearson 最高的未用列（默认）。hungarian=Pearson 总和最大的一一匹配。pong=允许上一 K 的一列拆成两列（Behr 2016），align.tsv 第三列为 pong 相似度并多一列 split_parent。jaccard=按人的集合算 Jaccard 后一一匹配，见 --jaccard-set。clumpp-full 在上一份 Q 右侧补一列 0，枚举下一份 Q 的全部列排列使 G' 最大，并列时取字典序最小的排列，并且在 K+1 大于 8 时停止。clumpp-greedy 在单个 K 到 K+1 的一对矩阵上与 clumpp-full 返回同一排列，已发表的 Greedy 只在同一个 K 有多于两次运行时才不同。clumpp-largek 同样补一列 0，按列 G' 反复锁定尚未使用的最高列对，分数相同则先取较小的新列号，再取较小的旧列号。",
    },
    "help_jaccard_set": {
        "en": "Set used by jaccard. dominant: this column is the person's highest column. threshold: this person's value in the column is >= --jaccard-cut. Default dominant",
        "zh": "jaccard 用的集合：dominant=该列是此人最高的列；threshold=此人该列 >= --jaccard-cut。默认 dominant",
    },
    "help_jaccard_cut": {
        "en": "Cutoff for the threshold set. Default 0.5",
        "zh": "threshold 集合的阈值。默认 0.5",
    },
    "help_align_report": {
        "en": "Also write align_report.tsv and align_report.txt",
        "zh": "另写 align_report.tsv 和 align_report.txt",
    },
    "help_align_report_low": {
        "en": "Low-confidence cutoff. Default 0.5 for greedy/hungarian/jaccard, and 0.8 for pong",
        "zh": "低置信阈值。默认 greedy/hungarian/jaccard 0.5，pong 0.8",
    },
    "help_align_groups": {
        "en": "Groups that take part in alignment, comma-separated. Required for core mode",
        "zh": "参与对齐的组，逗号分隔。core 模式必填",
    },
    "help_qmax": {
        "en": "qmax cutoff for core mode. Default 0.75",
        "zh": "core 模式的 qmax 阈值。默认 0.75",
    },
    "help_anchor_group": {
        "en": "When aligning, only the lowest K changes: that group's purest person's main column is placed at C1. With --no-align, or when there is only one K, every K does this.",
        "zh": "对齐时只改最低 K，把这个组最纯的人的主列放到 C1。--no-align 或只有一个 K 时，每个 K 都这样做。",
    },
    "help_color": {
        "en": "group=#rrggbb or C3=#rrggbb, split at the first equals sign. A group name cannot contain an equals sign. Repeatable",
        "zh": "组名=#rrggbb 或 C3=#rrggbb，在第一个等号处分开。组名不能含等号。可重复",
    },
    "help_color_file": {
        "en": "Two columns: name and #rrggbb",
        "zh": "两列：名字 #rrggbb",
    },
    "help_width": {
        "en": "Bar plot width, in pixels",
        "zh": "条形图宽度，像素",
    },
    "help_bar_height": {
        "en": "Height of each bar row. Default 220 for a single K, and 120 when there is more than one K",
        "zh": "每一行条的高度。单个 K 默认 220，多个 K 默认 120",
    },
    "help_provenance": {
        "en": "Also write run.json, recording the version, options, input hashes, and dependency versions",
        "zh": "另写 run.json，记下版本、选项、输入哈希和依赖版本",
    },
    "help_language": {
        "en": "Language for help, errors, and warnings. en or zh",
        "zh": "帮助、报错和警告的语言。en 或 zh",
    },
    "within_group_syntax": {
        "en": "--within-group must look like group=iid|q|hclust|input, got %(item)s",
        "zh": "--within-group 写成 组名=iid|q|hclust|input，收到 %(item)s",
    },
    "within_mode": {
        "en": "Within-group order must be one of %(modes)s, got %(mode)s",
        "zh": "组内排序只能是 %(modes)s，收到 %(mode)s",
    },
    "within_group_missing": {
        "en": "Warning: these groups in --within-group are not in the samples: %(names)s",
        "zh": "注意：--within-group 里这些组在样本中没有：%(names)s",
    },
    "missing_q_for_k": {
        "en": "%(name)s=%(k)s has no Q file",
        "zh": "%(name)s=%(k)s 没有对应的 Q",
    },
    "sort_col_range": {
        "en": "--sort-col must be between 1 and %(k)s",
        "zh": "--sort-col 要在 1 到 %(k)s 之间",
    },
    "order_file_ignores_blocks": {
        "en": "--order-file is set, so --blocks is not used",
        "zh": "给了 --order-file，--blocks 不用",
    },
    "q_format": {
        "en": "Q format must be admixture, meanq, or qopt, got %(format)s",
        "zh": "Q 格式只能是 admixture、meanq、qopt，收到 %(format)s",
    },
    "color_hex": {
        "en": "A color must be written as #rrggbb, got %(text)s",
        "zh": "颜色要写成 #rrggbb，收到 %(text)s",
    },
    "flag_and": {
        "en": " and ",
        "zh": " 和 ",
    },
    "id_sources_one": {
        "en": "%(flags)s: keep only one",
        "zh": "%(flags)s 只留一个",
    },
    "missing_ids": {
        "en": "Need --fam (PLINK .fam) or --ids (one IID per line, in the same order as the Q rows)",
        "zh": "需要 --fam（PLINK .fam）或 --ids（一行一个 IID，顺序与 Q 的行一致）",
    },
    "ids_extra": {
        "en": "Warning: --ids has %(n)s lines with more than one field; only the first field on each line was kept. Example: %(example)s",
        "zh": "注意：--ids 有 %(n)s 行含有多个字段，只保留了每行第一个。例如：%(example)s",
    },
    "duplicate_sample_names": {
        "en": "Duplicate sample names: %(path)s",
        "zh": "样本名有重复：%(path)s",
    },
    "empty_sample_list": {
        "en": "The sample list is empty: %(path)s",
        "zh": "样本名单是空的：%(path)s",
    },
    "groups_no_header": {
        "en": "The group table has no header: %(path)s",
        "zh": "分组表没有表头：%(path)s",
    },
    "groups_missing_column": {
        "en": "The group table has no column %(id_col)s / %(group_col)s. Columns present: %(columns)s",
        "zh": "分组表里没有列 %(id_col)s / %(group_col)s。现有列：%(columns)s",
    },
    "dir_empty_admixture": {
        "en": "The directory has no .Q or .q files: %(path)s",
        "zh": "目录里没有 .Q 或 .q：%(path)s",
    },
    "dir_empty_meanq": {
        "en": "The directory has no .meanQ or .meanq files: %(path)s",
        "zh": "目录里没有 .meanQ 或 .meanq：%(path)s",
    },
    "dir_empty_qopt": {
        "en": "The directory has no .qopt or .QOPT files: %(path)s",
        "zh": "目录里没有 .qopt 或 .QOPT：%(path)s",
    },
    "no_q_match": {
        "en": "No Q files matched: %(item)s",
        "zh": "没有匹配到 Q：%(item)s",
    },
    "no_q_files": {
        "en": "No Q files",
        "zh": "没有 Q 文件",
    },
    "q_not_found": {
        "en": "Q file not found: %(path)s",
        "zh": "找不到 Q：%(path)s",
    },
    "q_not_numeric": {
        "en": "Q must be whitespace-separated numbers: %(path)s",
        "zh": "Q 只能是空白分隔的数字：%(path)s",
    },
    "q_not_matrix": {
        "en": "Q is empty or is not a matrix: %(path)s",
        "zh": "Q 是空的或不是矩阵：%(path)s",
    },
    "bad_extension": {
        "en": "%(path)s does not have the extension for format %(format)s",
        "zh": "%(path)s 的扩展名不符合格式 %(format)s",
    },
    "filename_k": {
        "en": "%(path)s filename says K=%(k_file)s, but the column count is %(k_col)s",
        "zh": "%(path)s 文件名是 K=%(k_file)s，列数是 %(k_col)s",
    },
    "duplicate_k": {
        "en": "K=%(k)s has two Q files: %(path_a)s and %(path_b)s",
        "zh": "K=%(k)s 有两个 Q：%(path_a)s 和 %(path_b)s",
    },
    "row_count": {
        "en": "K=%(k)s Q has %(nrows)s rows, but the sample list has %(n)s rows",
        "zh": "K=%(k)s 的 Q 有 %(nrows)s 行，样本名单有 %(n)s 行",
    },
    "q_out_of_range": {
        "en": "K=%(k)s Q has a value outside [0,1]",
        "zh": "K=%(k)s 的 Q 有超出 [0,1] 的数",
    },
    "q_nan": {
        "en": "K=%(k)s Q contains NaN",
        "zh": "K=%(k)s 的 Q 有 NaN",
    },
    "row_sum_warn": {
        "en": "Warning: K=%(k)s has %(n)s people whose ancestry shares differ from 1 by more than 0.05; the extra part is left blank on the plot",
        "zh": "注意：K=%(k)s 有 %(n)s 行人的组分和离 1 超过 0.05，图上多出来的部分留白",
    },
    "order_empty": {
        "en": "The order file is empty: %(path)s",
        "zh": "顺序文件是空的：%(path)s",
    },
    "order_duplicate": {
        "en": "The order file has duplicate sample names: %(path)s",
        "zh": "顺序文件里有重复的样本名：%(path)s",
    },
    "order_unknown_names": {
        "en": "The order file has %(n)s names that are not in the sample list, for example %(examples)s",
        "zh": "顺序文件里有 %(n)s 个名字不在样本名单中，例如 %(examples)s",
    },
    "order_short": {
        "en": "The order file is missing %(n)s people; those %(n_same)s people are appended in sample-list order",
        "zh": "顺序文件少了 %(n)s 人，这 %(n_same)s 人按原名单顺序接在最后",
    },
    "color_file_line": {
        "en": 'Each line of the color file must be "name  #rrggbb": %(line)s',
        "zh": "颜色文件每行要是「名字  #rrggbb」：%(line)s",
    },
    "color_syntax": {
        "en": "A color must be written as group=#rrggbb or C3=#rrggbb, got %(item)s",
        "zh": "颜色写成 组名=#rrggbb 或 C3=#rrggbb，收到 %(item)s",
    },
    "duplicate_color": {
        "en": "Internal error: K=%(k)s has a duplicate color",
        "zh": "内部错误：K=%(k)s 的颜色有重复",
    },
    "narrow_group": {
        "en": "Warning: group %(name)s has a bar narrower than 14 pixels, so the group name is not drawn",
        "zh": "注意：组 %(name)s 的条宽小于 14 像素，图上没写组名",
    },
    "hclust_dist": {
        "en": "--hclust-dist must be one of %(choices)s",
        "zh": "--hclust-dist 只能是 %(choices)s",
    },
    "hclust_linkage": {
        "en": "--hclust-linkage must be one of %(choices)s",
        "zh": "--hclust-linkage 只能是 %(choices)s",
    },
    "ward_needs_euclidean": {
        "en": "--hclust-linkage ward requires --hclust-dist euclidean, got %(dist)s",
        "zh": "--hclust-linkage ward 需要 --hclust-dist euclidean，收到 %(dist)s",
    },
    "hclust_needs_scipy": {
        "en": "hclust requires scipy (scipy.cluster.hierarchy)",
        "zh": "hclust 需要 scipy（scipy.cluster.hierarchy）",
    },
    "hclust_nonfinite": {
        "en": "hclust distance was not finite (--hclust-dist %(dist)s)",
        "zh": "hclust 距离出现了非有限值（--hclust-dist %(dist)s）",
    },
    "hclust_pre": {
        "en": "--hclust-pre must be one of %(choices)s",
        "zh": "--hclust-pre 只能是 %(choices)s",
    },
    "sort_needs_q": {
        "en": "Sorting by ancestry share needs the Q matrix for that K",
        "zh": "按组分排序需要对应 K 的 Q",
    },
    "unknown_within": {
        "en": "Unknown within-group order: %(mode)s",
        "zh": "未知的组内排序：%(mode)s",
    },
    "order_not_permutation": {
        "en": "The order is not a permutation of every sample",
        "zh": "排序结果不是全体样本的一个排列",
    },
    "anchor_missing": {
        "en": "Anchor group %(anchor)s has no one in the samples",
        "zh": "锚定组 %(anchor)s 在样本里没有人",
    },
    "align_empty_check": {
        "en": "Nobody is left for alignment. Check --align-groups and --qmax",
        "zh": "对齐用的人是空的。检查 --align-groups 和 --qmax",
    },
    "clumpp_perm_limit": {
        "en": "--align-method %(method)s searches every permutation and stops when K+1 > 8 (here K+1 = %(k1)s). Use clumpp-largek or clumppling-ilp.",
        "zh": "--align-method %(method)s 会枚举所有排列，K+1 > 8 时停止（这里 K+1 = %(k1)s）。请用 clumpp-largek 或 clumppling-ilp。",
    },
    "align_needs_scipy": {
        "en": "--align-method %(method)s requires scipy (scipy.optimize)",
        "zh": "--align-method %(method)s 需要 scipy（scipy.optimize）",
    },
    "k_columns_differ": {
        "en": "Alignment requires consecutive K, and adjacent Q files must differ by 1 column",
        "zh": "对齐要求 K 连续，相邻两个 Q 的列数必须差 1",
    },
    "align_one_new_column": {
        "en": "Alignment should leave exactly 1 new column",
        "zh": "对齐后应该只剩 1 个新列",
    },
    "k_gap": {
        "en": "Cross-K alignment requires consecutive K. Missing K=%(k)s",
        "zh": "要跨 K 对齐，K 必须连续。缺 K=%(k)s",
    },
    "core_needs_groups": {
        "en": "align-mode core requires --align-groups",
        "zh": "align-mode core 需要 --align-groups",
    },
    "align_empty": {
        "en": "Nobody is left for alignment",
        "zh": "对齐用的人是空的",
    },
    "pearson_low": {
        "en": "Warning: K=%(k_from)s to %(k_to)s has %(n)s columns with Pearson < 0.5, so these two runs may not be the same solution",
        "zh": "注意：K=%(k_from)s\u2192%(k_to)s 有 %(n)s 列的 Pearson < 0.5，这两次的列可能不是同一个解",
    },
    "help_logs": {
        "en": "ADMIXTURE stdout files, a quoted wildcard, or a directory. A directory reads .out and .log. Default is off.",
        "zh": "ADMIXTURE 的标准输出，或带引号的通配符，或一个目录。目录读取 .out 和 .log。默认不读。",
    },
    "help_logs_map": {
        "en": "Two columns, log path and Q path, no header. Each log must be one of the --logs files, and each Q path must exist.",
        "zh": "两列，日志路径和 Q 路径，没有表头。每条日志必须在 --logs 里，Q 路径必须存在。",
    },
    "logs_dir_empty": {
        "en": "The directory has no .out or .log files: %(path)s",
        "zh": "目录里没有 .out 或 .log：%(path)s",
    },
    "logs_no_match": {
        "en": "No log files matched: %(item)s",
        "zh": "没有匹配到日志：%(item)s",
    },
    "logs_none": {
        "en": "No log files",
        "zh": "没有日志",
    },
    "logs_map_requires": {
        "en": "--logs-map requires --logs",
        "zh": "--logs-map 需要 --logs",
    },
    "logs_map_dup": {
        "en": "Duplicate log in --logs-map: %(path)s",
        "zh": "--logs-map 里的日志重复：%(path)s",
    },
    "logs_map_no_row": {
        "en": "Log %(path)s has no row in --logs-map",
        "zh": "日志 %(path)s 在 --logs-map 里没有一行",
    },
    "logs_map_not_in_logs": {
        "en": "Log %(path)s is not in --logs",
        "zh": "日志 %(path)s 不在 --logs 里",
    },
    "logs_map_line": {
        "en": "%(path)s map line must be log path and Q path: %(line)s",
        "zh": "%(path)s 的对照行必须是日志路径和 Q 路径：%(line)s",
    },
    "logs_map_q_missing": {
        "en": "Mapped Q file not found: %(path)s",
        "zh": "对照表里的 Q 找不到：%(path)s",
    },
    "logs_map_missing": {
        "en": "Log map not found: %(path)s",
        "zh": "对照表找不到：%(path)s",
    },
    "log_not_found": {
        "en": "Log file not found: %(path)s",
        "zh": "找不到日志：%(path)s",
    },
    "log_format": {
        "en": "%(path)s does not match the ADMIXTURE log format: %(line)s",
        "zh": "%(path)s 不符合 ADMIXTURE 日志格式：%(line)s",
    },
    "log_no_cv": {
        "en": "Warning: %(path)s has no CV error line",
        "zh": "注意：%(path)s 没有 CV error 行",
    },
    "log_truncated": {
        "en": "Warning: %(path)s is truncated",
        "zh": "注意：%(path)s 被截断",
    },
    "help_select_k": {
        "en": "Also write select_k.tsv, select_k.txt, and plots from the CV and log-likelihood table. These are heuristics.",
        "zh": "另写 select_k.tsv、select_k.txt 和图，数据来自 CV 和对数似然表。这些只是启发式。",
    },
    "help_plateau_fraction": {
        "en": "Plateau cut for --select-k. 0.05 is an arbitrary qbar default, not a published constant.",
        "zh": "--select-k 的平台阈值。0.05 是 qbar 自己定的默认值，不是文献里的常数。",
    },
    "select_k_requires": {
        "en": "--select-k requires --logs",
        "zh": "--select-k 需要 --logs",
    },
    "help_replicates": {
        "en": "Accept several Q files at one K, group them into modes, and align the major-mode mean across K. Off by default.",
        "zh": "同一个 K 接受多份 Q，分成模式，用主模式的均值做跨 K 对齐。默认关闭。",
    },
    "help_mode_sim_cut": {
        "en": "Similarity at or above which two replicates are linked into one mode. Required with --replicates. Not calibrated.",
        "zh": "两份重复的相似度达到或超过这个值就归入同一模式。使用 --replicates 时必填。未校准。",
    },
    "replicates_requires_cut": {
        "en": "--replicates requires --mode-sim-cut. No default cut is shipped because none has been calibrated.",
        "zh": "--replicates 需要 --mode-sim-cut。尚未校准，所以不提供默认阈值。",
    },
    "mode_sim_cut_requires": {
        "en": "--mode-sim-cut requires --replicates",
        "zh": "--mode-sim-cut 需要 --replicates",
    },
    "mode_sim_cut_range": {
        "en": "--mode-sim-cut must be between 0 and 1, got %(cut)s",
        "zh": "--mode-sim-cut 必须在 0 和 1 之间，收到 %(cut)s",
    },
    "mode_mean_zero_row": {
        "en": "Mode %(mode)s at K=%(k)s has a row whose mean sums to 0",
        "zh": "K=%(k)s 的模式 %(mode)s 有一行均值和为 0",
    },
    "replicate_needs_scipy": {
        "en": "Replicate alignment requires scipy (scipy.optimize)",
        "zh": "重复对齐需要 scipy（scipy.optimize）",
    },
    "replicate_method": {
        "en": "Alignment method must be one of %(methods)s, got %(method)s",
        "zh": "对齐方法只能是 %(methods)s，收到 %(method)s",
    },
    "replicate_jaccard_set": {
        "en": "--jaccard-set must be one of %(choices)s, got %(kind)s",
        "zh": "--jaccard-set 只能是 %(choices)s，收到 %(kind)s",
    },
    "replicate_shape": {
        "en": "Replicates at one K must have the same shape, got %(path)s",
        "zh": "同一个 K 的重复必须形状相同，收到 %(path)s",
    },
    "replicate_empty": {
        "en": "modes_for_k needs at least one matrix",
        "zh": "modes_for_k 至少需要一个矩阵",
    },
}


def text(key, language="en", **values):
    """Return the user-facing string for ``key``.

    ``language`` is ``en`` or ``zh``. Placeholders in the string are
    filled from ``values``.
    """
    try:
        template = _CATALOG[key][language]
    except KeyError as exc:
        raise KeyError("message %s language %s" % (key, language)) from exc
    if not values:
        return template
    return template % values
