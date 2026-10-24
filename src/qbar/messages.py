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
        "en": "all: everyone in the mask is used for alignment, and greedy, hungarian, pong, jaccard, clumpp-full, clumpp-greedy, clumpp-largek, and clumppling-ilp use the same people. Pearson is used only for greedy and hungarian. core: keep only people whose qmax is strictly greater than --qmax at both adjacent K; if a group has nobody above that cut, keep that group's purest person at the lower K",
        "zh": "all=掩码内所有人参与对齐，greedy、hungarian、pong、jaccard、clumpp-full、clumpp-greedy、clumpp-largek、clumppling-ilp 用同一批人。Pearson 只用于 greedy 和 hungarian。core=只留相邻两个 K 的 qmax 都严格大于 --qmax 的人；某一组没有人超过时，留下该组在较低 K 上最纯的一个人",
    },
    "help_align_method": {
        "en": "greedy takes the unused column with the highest Pearson value, one old column at a time (default). hungarian is the one-to-one match with the largest sum of Pearson values. pong allows one column from the previous K to split into two (Behr 2016); column 3 of align.tsv is the pong similarity and an extra split_parent column is written. jaccard matches one-to-one on sets of people; see --jaccard-set. clumpp-full pads the previous Q with one zero column and searches every permutation of the next Q to maximize G', keeping the lexicographically smallest permutation on a tie, and stops when K+1 is above 8. clumpp-greedy returns the same permutation as clumpp-full on one K to K+1 pair; the published Greedy differs only with more than two runs at one K. clumpp-largek pads the previous Q with one zero column and repeatedly locks the highest remaining column pair by column G', breaking ties by the smaller new-column index and then the smaller old-column index. clumppling-ilp assigns each column of the next Q to one column of the previous Q, requires every previous column to receive at least one, minimizes that squared-difference cost, and places the extra column last.",
        "zh": "greedy=按列顺序逐列取 Pearson 最高的未用列（默认）。hungarian=Pearson 总和最大的一一匹配。pong=允许上一 K 的一列拆成两列（Behr 2016），align.tsv 第三列为 pong 相似度并多一列 split_parent。jaccard=按人的集合算 Jaccard 后一一匹配，见 --jaccard-set。clumpp-full 在上一份 Q 右侧补一列 0，枚举下一份 Q 的全部列排列使 G' 最大，并列时取字典序最小的排列，并且在 K+1 大于 8 时停止。clumpp-greedy 在单个 K 到 K+1 的一对矩阵上与 clumpp-full 返回同一排列，已发表的 Greedy 只在同一个 K 有多于两次运行时才不同。clumpp-largek 同样补一列 0，按列 G' 反复锁定尚未使用的最高列对，分数相同则先取较小的新列号，再取较小的旧列号。clumppling-ilp 把下一份 Q 的每一列分给上一份 Q 的一列，要求每一旧列至少分到一列，并最小化列差的平方代价，多出来的那一列放在最后。",
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
    "help_align_compare": {
        "en": "Also write align_compare.tsv and align_compare.txt, comparing every available align method with the chosen one. No method is declared better.",
        "zh": "另写 align_compare.tsv 和 align_compare.txt，把每种可用的对齐方法和当前方法对照。不判定哪种更好。",
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
    "help_palette": {
        "en": "Bar colours: science, classic, tab10, set1, dark2, or paired. Default science. classic is the previous 20 colours.",
        "zh": "条的颜色：science、classic、tab10、set1、dark2 或 paired。默认 science。classic 是原来的 20 色。",
    },
    "help_color_lock": {
        "en": "off or on. Default off. on keeps each aligned column's colour from the lowest K, unless --color sets that column.",
        "zh": "off 或 on。默认 off。on 时每列沿用最低 K 的颜色，除非 --color 指定该列。",
    },
    "help_greyscale_preview": {
        "en": "Also write panel_grey.png. Each pixel is round(0.2126*R + 0.7152*G + 0.0722*B) on all three channels. Default off.",
        "zh": "另写 panel_grey.png。每个像素三通道都是 round(0.2126*R + 0.7152*G + 0.0722*B)。默认关闭。",
    },
    "palette_choice": {
        "en": "--palette must be science, classic, tab10, set1, dark2, or paired, got %(name)s",
        "zh": "--palette 只能是 science、classic、tab10、set1、dark2 或 paired，收到 %(name)s",
    },
    "color_lock_choice": {
        "en": "--color-lock must be off or on, got %(mode)s",
        "zh": "--color-lock 只能是 off 或 on，收到 %(mode)s",
    },
    "help_vector": {
        "en": "off, pdf, svg, or both. Default off. off keeps the PNG and the raster PDF. pdf writes bar_K*.pdf and panel.pdf as vectors. svg also writes bar_K*.svg and panel.svg, and the PDF stays raster. both writes vector PDFs and SVGs. PNG stays raster. A vector file with more than 200000 bar rectangles is refused and no output file is written.",
        "zh": "off、pdf、svg 或 both。默认 off。off 保持 PNG 和栅格 PDF。pdf 把 bar_K*.pdf 和 panel.pdf 写成矢量。svg 另写 bar_K*.svg 和 panel.svg，PDF 仍是栅格。both 写矢量 PDF 和 SVG。PNG 始终是栅格。单个矢量文件的条形矩形超过 200000 就拒绝，并且不写任何输出文件。",
    },
    "vector_choice": {
        "en": "--vector must be off, pdf, svg, or both, got %(got)s",
        "zh": "--vector 只能是 off、pdf、svg 或 both，收到 %(got)s",
    },
    "vector_rect_cap": {
        "en": "Vector file %(kind)s would draw %(count)s rectangles, above the cap of %(cap)s. No file was written.",
        "zh": "矢量文件 %(kind)s 要画 %(count)s 个矩形，超过上限 %(cap)s。没有写出文件。",
    },
    "vector_font_missing": {
        "en": "Vector output needs a TrueType file, and none of the font candidates exists.",
        "zh": "矢量输出需要一个 TrueType 文件，候选字体都不存在。",
    },
    "vector_pdf_ascii": {
        "en": "Vector PDF supports ASCII text only, and cannot draw the label %(label)s. No file was written.",
        "zh": "矢量 PDF 只支持 ASCII 文本，不能绘制标签 %(label)s。没有写出文件。",
    },
    "vector_ext": {
        "en": "Vector output path must end in .pdf or .svg, got %(path)s",
        "zh": "矢量路径必须以 .pdf 或 .svg 结尾，收到 %(path)s",
    },
    "help_html": {
        "en": "Also write panel.html, one offline file. A script draws the bars on a canvas and hover text shows the sample. Default off.",
        "zh": "另写 panel.html，一个离线文件。脚本在画布上画条，悬停显示样本。默认关闭。",
    },
    "html_empty": {
        "en": "HTML panel needs at least one K.",
        "zh": "HTML 面板至少需要一个 K。",
    },
    "html_rows": {
        "en": "HTML panel needs %(n)s rows, got %(n_id)s ids and %(n_group)s groups.",
        "zh": "HTML 面板需要 %(n)s 行，收到 %(n_id)s 个 id 和 %(n_group)s 个分组。",
    },
    "html_order": {
        "en": "HTML panel order must list each row once, got %(got)s entries for %(n)s rows.",
        "zh": "HTML 面板的顺序必须每一行恰好出现一次，收到 %(got)s 项，行数是 %(n)s。",
    },
    "html_shape": {
        "en": "HTML panel K=%(k)s has %(rows)s rows, expected %(n)s.",
        "zh": "HTML 面板 K=%(k)s 有 %(rows)s 行，应为 %(n)s。",
    },
    "html_hex": {
        "en": "HTML panel K=%(k)s has %(cols)s columns and %(n_hex)s colours.",
        "zh": "HTML 面板 K=%(k)s 有 %(cols)s 列和 %(n_hex)s 个颜色。",
    },
    "html_missing_hex": {
        "en": "HTML panel has no colours for K=%(k)s.",
        "zh": "HTML 面板没有 K=%(k)s 的颜色。",
    },
    "html_runs": {
        "en": "HTML panel runs has %(got)s labels for %(n)s values of K.",
        "zh": "HTML 面板的 run 有 %(got)s 个标签，K 有 %(n)s 个。",
    },
    "html_width": {
        "en": "HTML panel width must be at least 1 pixel, got %(width)s.",
        "zh": "HTML 面板宽度至少 1 像素，收到 %(width)s。",
    },
    "html_height": {
        "en": "HTML panel row height must be at least 1 pixel, got %(height)s.",
        "zh": "HTML 面板行高至少 1 像素，收到 %(height)s。",
    },
    "html_legend": {
        "en": "HTML panel legend has %(got)s rows for %(n)s values of K.",
        "zh": "HTML 面板的图例有 %(got)s 行，K 有 %(n)s 个。",
    },
    "vector_rows": {
        "en": "Vector output needs the Q matrix on each bar row.",
        "zh": "矢量输出需要每一行条上的 Q 矩阵。",
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
    "clumppling_needs_scipy": {
        "en": "clumppling-ilp needs scipy>=1.9.0 (scipy.optimize.milp)",
        "zh": "clumppling-ilp 需要 scipy>=1.9.0（scipy.optimize.milp）",
    },
    "clumppling_not_optimal": {
        "en": "clumppling-ilp did not reach an optimal solution (status %(status)s: %(message)s)",
        "zh": "clumppling-ilp 没有得到最优解（status %(status)s：%(message)s）",
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
    "help_bootstrap": {
        "en": "Resample individuals with replacement this many times and write match_support.tsv. Default 0 writes no file.",
        "zh": "按个体有放回重抽样这么多次，并写 match_support.tsv。默认 0，不写文件。",
    },
    "help_bootstrap_seed": {
        "en": "Seed for --bootstrap. Used only when --bootstrap is greater than 0. Default 0.",
        "zh": "--bootstrap 的种子。仅在 --bootstrap 大于 0 时使用。默认 0。",
    },
    "bootstrap_negative": {
        "en": "--bootstrap must be an integer greater than or equal to 0, got %(n)s",
        "zh": "--bootstrap 必须是大于或等于 0 的整数，收到 %(n)s",
    },
    "bootstrap_seed_negative": {
        "en": "--bootstrap-seed must be an integer greater than or equal to 0, got %(seed)s",
        "zh": "--bootstrap-seed 必须是大于或等于 0 的整数，收到 %(seed)s",
    },
    "bootstrap_replicate_failed": {
        "en": "Bootstrap replicate %(n)s failed: %(detail)s",
        "zh": "Bootstrap 第 %(n)s 次失败：%(detail)s",
    },
    "bootstrap_row_count": {
        "en": "Bootstrap needs the same row count at every K",
        "zh": "Bootstrap 要求每个 K 的行数相同",
    },
    "bootstrap_group_rows": {
        "en": "Bootstrap expected %(rows)s group labels, got %(got)s",
        "zh": "Bootstrap 需要 %(rows)s 个组名，收到 %(got)s",
    },
    "bootstrap_mask_shape": {
        "en": "Bootstrap mask has %(got)s entries, expected %(rows)s rows",
        "zh": "Bootstrap 掩码有 %(got)s 项，应为 %(rows)s 行",
    },
    "help_perm": {
        "en": "Permute this many times and append n_perm, n_extreme, p, null, and zero_column to match_support.tsv. Default 0 adds no columns. When this is greater than 0, --perm-null is required.",
        "zh": "置换这么多次，并在 match_support.tsv 追加 n_perm、n_extreme、p、null、zero_column。默认 0，不追加列。大于 0 时必须给出 --perm-null。",
    },
    "help_perm_seed": {
        "en": "Seed for --perm. Used only when --perm is greater than 0. Default 0.",
        "zh": "--perm 的种子。仅在 --perm 大于 0 时使用。默认 0。",
    },
    "help_perm_null": {
        "en": "Null used when --perm is greater than 0. rows shuffles the K+1 matrix row order and reruns that one match. column shuffles the matched new column across individuals and recomputes its similarity. Required when --perm is greater than 0.",
        "zh": "--perm 大于 0 时的零假设。rows 打乱 K+1 矩阵的行序并重跑这一步匹配。column 在个体间打乱被匹配的新列并重算相似度。大于 0 时必填。",
    },
    "perm_negative": {
        "en": "--perm must be an integer greater than or equal to 0, got %(n)s",
        "zh": "--perm 必须是大于或等于 0 的整数，收到 %(n)s",
    },
    "perm_seed_negative": {
        "en": "--perm-seed must be an integer greater than or equal to 0, got %(seed)s",
        "zh": "--perm-seed 必须是大于或等于 0 的整数，收到 %(seed)s",
    },
    "perm_null_required": {
        "en": "--perm requires --perm-null when --perm is greater than 0. Choices are rows and column.",
        "zh": "--perm 大于 0 时必须给出 --perm-null。可选 rows 和 column。",
    },
    "perm_null_choice": {
        "en": "--perm-null must be rows or column, got %(null)s",
        "zh": "--perm-null 只能是 rows 或 column，收到 %(null)s",
    },
    "perm_column_range": {
        "en": "Permutation column %(column)s is outside 0..%(last)s",
        "zh": "置换列 %(column)s 不在 0..%(last)s 内",
    },
    "perm_not_matrix": {
        "en": "--perm needs two matrices with 2 dimensions",
        "zh": "--perm 需要两个二维矩阵",
    },
    "perm_row_count": {
        "en": "--perm needs the same row count in both matrices, got %(prev)s and %(new)s",
        "zh": "--perm 需要两个矩阵行数相同，收到 %(prev)s 和 %(new)s",
    },
    "perm_group_rows": {
        "en": "--perm expected %(rows)s group labels, got %(got)s",
        "zh": "--perm 需要 %(rows)s 个组名，收到 %(got)s",
    },
    "perm_mask_shape": {
        "en": "--perm mask has %(got)s entries, expected %(rows)s rows",
        "zh": "--perm 掩码有 %(got)s 项，应为 %(rows)s 行",
    },
    "perm_internal": {
        "en": "Permutation row count does not match the alignment",
        "zh": "置换行数和对齐结果不一致",
    },
    "help_parent_ci": {
        "en": "Write parent_share_ci.tsv with a percentile interval for the largest parent share. Off by default. Requires --bootstrap greater than 0. Uses the same row resamples as --bootstrap.",
        "zh": "写 parent_share_ci.tsv，给出最大父列份额的百分位区间。默认关闭。需要 --bootstrap 大于 0。",
    },
    "help_parent_alpha": {
        "en": "Two-sided alpha for --parent-ci. Default 0.05. Must be greater than 0 and less than 1.",
        "zh": "--parent-ci 的 alpha。默认 0.05。必须大于 0 且小于 1。",
    },
    "help_parent_test": {
        "en": "Add a residual test of one parent versus two to parent_share_ci.tsv. Off by default. Requires --perm greater than 0. Uses --perm and --perm-seed.",
        "zh": "在 parent_share_ci.tsv 里检验一个父列还是两个。默认关闭。需要 --perm 大于 0。",
    },
    "parent_ci_needs_bootstrap": {
        "en": "--parent-ci requires --bootstrap greater than 0. Set --bootstrap.",
        "zh": "--parent-ci 需要设置 --bootstrap。",
    },
    "parent_test_needs_perm": {
        "en": "--parent-test requires --perm greater than 0. Set --perm.",
        "zh": "--parent-test 需要设置 --perm。",
    },
    "parent_alpha_range": {
        "en": "--parent-alpha must be greater than 0 and less than 1, got %(alpha)s",
        "zh": "--parent-alpha 必须大于 0 且小于 1，收到 %(alpha)s",
    },
    "parent_shape": {
        "en": "one_vs_two needs a 2-d previous matrix, a 1-d new column, and the same row count",
        "zh": "one_vs_two 需要二维上一矩阵和一维新列，且行数相同",
    },
    "parent_mask_shape": {
        "en": "Parent-share mask has %(got)s entries, expected %(rows)s rows",
        "zh": "父列份额掩码有 %(got)s 项，应为 %(rows)s 行",
    },
    "parent_perm_negative": {
        "en": "n_perm must be an integer greater than or equal to 0, got %(n)s",
        "zh": "n_perm 必须是大于或等于 0 的整数，收到 %(n)s",
    },
    "parent_seed_negative": {
        "en": "seed must be an integer greater than or equal to 0, got %(seed)s",
        "zh": "seed 必须是大于或等于 0 的整数，收到 %(seed)s",
    },
    "parent_index_count": {
        "en": "Parent-share interval expected %(n)s bootstrap index vectors, got %(got)s",
        "zh": "父列份额区间需要 %(n)s 个 bootstrap 行下标，收到 %(got)s",
    },
    "help_low_confidence_table": {
        "en": "TSV with columns method, cut, precision, recall, n_matches, and split. With --align-report, copy those rows for the active align method onto the end of align_report.txt. Does not change the low-confidence cut.",
        "zh": "含 method、cut、precision、recall、n_matches、split 列的 TSV。与 --align-report 一起用时，把当前对齐方法的行抄到 align_report.txt 末尾。不改变低置信阈值。",
    },
    "lowconf_not_found": {
        "en": "--low-confidence-table file not found: %(path)s",
        "zh": "--low-confidence-table 文件不存在：%(path)s",
    },
    "lowconf_encoding": {
        "en": "--low-confidence-table is not UTF-8: %(path)s",
        "zh": "--low-confidence-table 不是 UTF-8：%(path)s",
    },
    "lowconf_no_header": {
        "en": "--low-confidence-table has no header: %(path)s",
        "zh": "--low-confidence-table 没有表头：%(path)s",
    },
    "lowconf_blank_column": {
        "en": "--low-confidence-table has a blank column name",
        "zh": "--low-confidence-table 有空的列名",
    },
    "lowconf_duplicate_column": {
        "en": "--low-confidence-table repeats column %(column)s",
        "zh": "--low-confidence-table 列 %(column)s 重复",
    },
    "lowconf_missing": {
        "en": "--low-confidence-table is missing columns: %(columns)s",
        "zh": "--low-confidence-table 缺少列：%(columns)s",
    },
    "lowconf_row_width": {
        "en": "--low-confidence-table row %(row)s has %(got)s fields and the header has %(want)s",
        "zh": "--low-confidence-table 第 %(row)s 行有 %(got)s 列，表头有 %(want)s 列",
    },
    "lowconf_empty_method": {
        "en": "--low-confidence-table row %(row)s has an empty method",
        "zh": "--low-confidence-table 第 %(row)s 行的 method 为空",
    },
    "lowconf_bad_number": {
        "en": "--low-confidence-table row %(row)s column %(column)s is not a number: %(value)s",
        "zh": "--low-confidence-table 第 %(row)s 行的 %(column)s 不是数字：%(value)s",
    },
    "lowconf_unused": {
        "en": "Warning: --low-confidence-table is unused without --align-report.",
        "zh": "注意：没有 --align-report 时不使用 --low-confidence-table。",
    },
    "lowconf_no_report": {
        "en": "Warning: --low-confidence-table is unused because this run wrote no alignment report.",
        "zh": "注意：这次没有写对齐报告，所以不使用 --low-confidence-table。",
    },
    "lowconf_block_note": {
        "en": "Copied rows for this align method. These rows do not change the low-confidence cut used above.",
        "zh": "当前对齐方法的抄录行。这些行不改变上面使用的低置信阈值。",
    },
    "lowconf_method_missing": {
        "en": "Warning: --low-confidence-table has no rows for method %(method)s. The low-confidence cut is unchanged.",
        "zh": "注意：--low-confidence-table 没有方法 %(method)s 的行。低置信阈值不变。",
    },
    "lowconf_length": {
        "en": "score_matches needs equal-length boolean sequences, got %(pred)s and %(truth)s",
        "zh": "score_matches 需要等长布尔序列，收到 %(pred)s 和 %(truth)s",
    },
    "lowconf_not_bool": {
        "en": "score_matches needs boolean values, got %(value)s",
        "zh": "score_matches 需要布尔值，收到 %(value)s",
    },
    "help_cluster_flow": {
        "en": "Write cluster_flow.tsv, cluster_flow.png, and cluster_flow.pdf. none writes nothing. sankey draws membership weight between aligned columns at consecutive K. Default none.",
        "zh": "写 cluster_flow.tsv、cluster_flow.png 和 cluster_flow.pdf。none 不写。sankey 画连续 K 的对齐列之间的成员权重。默认 none。",
    },
    "help_flow_weight": {
        "en": "Edge weight used only with --cluster-flow sankey. share is the destination parent share. jaccard is the member-set Jaccard. Default share.",
        "zh": "只在 --cluster-flow sankey 时作为边权重。share 是目标列的父列份额。jaccard 是成员集合 Jaccard。默认 share。",
    },
    "flow_weight_needs_sankey": {
        "en": "--flow-weight %(weight)s requires --cluster-flow sankey.",
        "zh": "--flow-weight %(weight)s 需要 --cluster-flow sankey。",
    },
    "flow_needs_align": {
        "en": "--cluster-flow sankey needs alignment across K; remove --no-align.",
        "zh": "--cluster-flow sankey 需要跨 K 对齐；去掉 --no-align。",
    },
    "flow_weight_choice": {
        "en": "--flow-weight must be share or jaccard, got %(weight)s",
        "zh": "--flow-weight 只能是 share 或 jaccard，收到 %(weight)s",
    },
    "flow_mode_choice": {
        "en": "--cluster-flow must be none or sankey, got %(mode)s",
        "zh": "--cluster-flow 只能是 none 或 sankey，收到 %(mode)s",
    },
    "flow_jaccard_set": {
        "en": "--jaccard-set must be dominant or threshold, got %(kind)s",
        "zh": "--jaccard-set 只能是 dominant 或 threshold，收到 %(kind)s",
    },
    "flow_not_matrix": {
        "en": "Cluster flow needs a 2-d matrix at each K",
        "zh": "聚类流需要每个 K 都是二维矩阵",
    },
    "flow_row_count": {
        "en": "Cluster flow needs the same row count at K=%(k_from)s and K=%(k_to)s, got %(prev)s and %(new)s",
        "zh": "聚类流需要 K=%(k_from)s 和 K=%(k_to)s 行数相同，收到 %(prev)s 和 %(new)s",
    },
    "flow_mask_shape": {
        "en": "Cluster-flow mask has %(got)s entries, expected %(rows)s rows",
        "zh": "聚类流掩码有 %(got)s 项，应为 %(rows)s 行",
    },
    "help_order_mode": {
        "en": "within orders inside groups (default). global-hclust clusters every row as one tree. group-hclust keeps each group contiguous.",
        "zh": "within=组内排序（默认）。global-hclust=所有人一棵树。group-hclust=每组保持连续。",
    },
    "help_group_order": {
        "en": "Group order for --order-mode group-hclust. input keeps the first-seen order (default). hclust orders groups by the mean Q row.",
        "zh": "group-hclust 的组顺序。input=按首次出现（默认）。hclust=按各组 Q 的均值排序。",
    },
    "help_dendrogram": {
        "en": "Dendrogram above the bars. none draws none (default). top is allowed for global-hclust, or for group-hclust with --group-order hclust.",
        "zh": "条形图上方的树状图。none=不画（默认）。top 只用于 global-hclust，或 group-hclust 且 --group-order hclust。",
    },
    "help_hclust_max_bytes": {
        "en": "Refuse before the distance vector when N*(N-1)/2*8 exceeds this many bytes. 0 means no cap. When omitted, global-hclust, the between-group tree, and --auto-groups hclust use 4294967296, and within-group trees have no cap.",
        "zh": "距离向量字节数 N*(N-1)/2*8 超过该值时，在建立向量前停止。0 表示不限制。省略时，global-hclust、组间树和 --auto-groups hclust 用 4294967296，组内树不限制。",
    },
    "hclust_over_cap": {
        "en": "Hierarchical clustering of N=%(n)s needs %(nbytes)s bytes (N*(N-1)/2*8), which is above --hclust-max-bytes %(cap)s. Use within-group clustering or --hclust-pre dominant.",
        "zh": "N=%(n)s 的层次聚类需要 %(nbytes)s 字节（N*(N-1)/2*8），超过 --hclust-max-bytes %(cap)s。请改用组内聚类或 --hclust-pre dominant。",
    },
    "hclust_max_bytes_negative": {
        "en": "--hclust-max-bytes must be 0 or greater, got %(cap)s.",
        "zh": "--hclust-max-bytes 必须大于等于 0，收到 %(cap)s。",
    },
    "hclust_max_bytes_type": {
        "en": "--hclust-max-bytes must be an integer, got %(cap)s.",
        "zh": "--hclust-max-bytes 必须是整数，收到 %(cap)s。",
    },
    "order_mode_choice": {
        "en": "--order-mode must be one of %(choices)s, got %(mode)s.",
        "zh": "--order-mode 只能是 %(choices)s，收到 %(mode)s。",
    },
    "group_order_choice": {
        "en": "--group-order must be one of %(choices)s, got %(mode)s.",
        "zh": "--group-order 只能是 %(choices)s，收到 %(mode)s。",
    },
    "dendrogram_choice": {
        "en": "--dendrogram must be one of %(choices)s, got %(mode)s.",
        "zh": "--dendrogram 只能是 %(choices)s，收到 %(mode)s。",
    },
    "group_order_needs_mode": {
        "en": "--group-order hclust requires --order-mode group-hclust.",
        "zh": "--group-order hclust 需要 --order-mode group-hclust。",
    },
    "dendrogram_needs_tree": {
        "en": "--dendrogram top needs --order-mode global-hclust, or --order-mode group-hclust with --group-order hclust.",
        "zh": "--dendrogram top 需要 --order-mode global-hclust，或 --order-mode group-hclust 且 --group-order hclust。",
    },
    "order_file_with_mode": {
        "en": "--order-file cannot be combined with --order-mode %(mode)s.",
        "zh": "--order-file 不能和 --order-mode %(mode)s 一起用。",
    },
    "hclust_tree_kind": {
        "en": "Internal error: unknown hclust tree %(tree)s.",
        "zh": "内部错误：未知的 hclust 树 %(tree)s。",
    },
    "group_hclust_shape": {
        "en": "group_hclust_order needs one group label per row, got %(groups)s labels and %(rows)s rows.",
        "zh": "group_hclust_order 需要每行一个组名，收到 %(groups)s 个组名和 %(rows)s 行。",
    },
    "blocks_ignored": {
        "en": "Warning: --blocks is not used when --order-mode is %(mode)s.",
        "zh": "注意：--order-mode 为 %(mode)s 时不使用 --blocks。",
    },
    "within_ignored_global": {
        "en": "Warning: --within and --within-group are not used when --order-mode is global-hclust.",
        "zh": "注意：--order-mode 为 global-hclust 时不使用 --within 和 --within-group。",
    },
    "dendrogram_leaf_count": {
        "en": "Dendrogram leaf count %(leaves)s does not match the linkage (%(obs)s observations).",
        "zh": "树状图叶数 %(leaves)s 和 linkage 的观测数 %(obs)s 不一致。",
    },
    "dendrogram_kind": {
        "en": "Internal error: unknown dendrogram layer %(kind)s.",
        "zh": "内部错误：未知的树状图层 %(kind)s。",
    },
    "help_auto_groups": {
        "en": "Write groups_auto.tsv. none writes nothing (default). major uses the highest column. threshold uses --admix-cut. hclust and kmeans need --auto-g and name groups G1, G2, ... hclust and kmeans can read --pca.",
        "zh": "写 groups_auto.tsv。none 不写（默认）。major 用最高列。threshold 用 --admix-cut。hclust 和 kmeans 需要 --auto-g，组名是 G1、G2。这两种也可以读 --pca。",
    },
    "help_auto_k": {
        "en": "K of the aligned matrix used for max_q, top_column, and Q clustering. Default: the largest K.",
        "zh": "用于 max_q、top_column 和 Q 聚类的对齐矩阵的 K。默认最大的 K。",
    },
    "help_admix_cut": {
        "en": "Strict cut for --auto-groups threshold. A row is admixed only when its maximum is below this cut. Must be above 0 and at most 1. Default 0.5.",
        "zh": "--auto-groups threshold 的严格阈值。最大值低于该值才标为 admixed。必须大于 0 且不超过 1。默认 0.5。",
    },
    "help_auto_g": {
        "en": "Number of groups for --auto-groups hclust or kmeans. Required for those methods. At least 1, and at most the row count.",
        "zh": "--auto-groups hclust 或 kmeans 的组数。这两种方法必须给出。至少为 1，且不能超过行数。",
    },
    "help_auto_seed": {
        "en": "Seed for --auto-groups kmeans. One numpy Generator draws the 10 restarts. Default 0.",
        "zh": "--auto-groups kmeans 的种子。一个 numpy Generator 抽出 10 次重启。默认 0。",
    },
    "help_pca": {
        "en": "PLINK 1.9 eigenvec for --auto-groups hclust or kmeans. No header: FID, IID, then scores. Rows match on IID. Requires --pca-n.",
        "zh": "给 --auto-groups hclust 或 kmeans 的 PLINK 1.9 eigenvec。无表头：FID、IID，然后是得分。按 IID 对齐。必须同时给 --pca-n。",
    },
    "help_pca_n": {
        "en": "How many leading score columns to use from --pca. Required with --pca. From 1 up to the number of score columns.",
        "zh": "从 --pca 取前几个得分列。和 --pca 一起必须给出。范围是 1 到文件里的得分列数。",
    },
    "auto_groups_choice": {
        "en": "--auto-groups must be none, major, threshold, hclust, or kmeans, got %(method)s.",
        "zh": "--auto-groups 只能是 none、major、threshold、hclust 或 kmeans，收到 %(method)s。",
    },
    "auto_k_needs_groups": {
        "en": "--auto-k %(k)s requires --auto-groups major, threshold, hclust, or kmeans.",
        "zh": "--auto-k %(k)s 需要 --auto-groups 为 major、threshold、hclust 或 kmeans。",
    },
    "admix_cut_needs_threshold": {
        "en": "--admix-cut %(cut)s requires --auto-groups threshold.",
        "zh": "--admix-cut %(cut)s 需要 --auto-groups threshold。",
    },
    "auto_g_needs_cluster": {
        "en": "--auto-g %(g)s requires --auto-groups hclust or kmeans.",
        "zh": "--auto-g %(g)s 需要 --auto-groups hclust 或 kmeans。",
    },
    "auto_g_required": {
        "en": "--auto-groups %(method)s requires --auto-g.",
        "zh": "--auto-groups %(method)s 需要 --auto-g。",
    },
    "auto_g_range": {
        "en": "--auto-g must be an integer >= 1, got %(g)s.",
        "zh": "--auto-g 必须是大于等于 1 的整数，收到 %(g)s。",
    },
    "auto_g_above_n": {
        "en": "--auto-g %(g)s is greater than the number of rows %(n)s.",
        "zh": "--auto-g %(g)s 大于行数 %(n)s。",
    },
    "auto_seed_needs_kmeans": {
        "en": "--auto-seed %(seed)s requires --auto-groups kmeans.",
        "zh": "--auto-seed %(seed)s 需要 --auto-groups kmeans。",
    },
    "pca_needs_cluster": {
        "en": "--pca requires --auto-groups hclust or kmeans.",
        "zh": "--pca 需要 --auto-groups hclust 或 kmeans。",
    },
    "pca_needs_n": {
        "en": "--pca requires --pca-n.",
        "zh": "--pca 需要 --pca-n。",
    },
    "pca_n_needs_pca": {
        "en": "--pca-n requires --pca.",
        "zh": "--pca-n 需要 --pca。",
    },
    "pca_n_low": {
        "en": "--pca-n must be an integer >= 1, got %(n)s.",
        "zh": "--pca-n 必须是大于等于 1 的整数，收到 %(n)s。",
    },
    "admix_cut_bounds": {
        "en": "--admix-cut must be above 0 and at most 1, got %(cut)s.",
        "zh": "--admix-cut 必须大于 0 且不超过 1，收到 %(cut)s。",
    },
    "auto_k_missing": {
        "en": "--auto-k %(k)s is not a loaded K.",
        "zh": "--auto-k %(k)s 不是已读入的 K。",
    },
    "pca_not_found": {
        "en": "--pca file not found: %(path)s",
        "zh": "找不到 --pca 文件：%(path)s",
    },
    "pca_empty": {
        "en": "--pca file is empty: %(path)s",
        "zh": "--pca 文件是空的：%(path)s",
    },
    "pca_layout": {
        "en": "%(path)s: only the PLINK 1.9 eigenvec layout is read (no header, FID, IID, then scores).",
        "zh": "%(path)s：只读取 PLINK 1.9 eigenvec（无表头，FID、IID，然后是得分）。",
    },
    "pca_blank": {
        "en": "%(path)s line %(line)s is empty. Rows are not skipped.",
        "zh": "%(path)s 第 %(line)s 行是空的。不跳过任何行。",
    },
    "pca_short": {
        "en": "%(path)s line %(line)s does not have FID, IID, and scores.",
        "zh": "%(path)s 第 %(line)s 行没有 FID、IID 和得分。",
    },
    "pca_score": {
        "en": "%(path)s line %(line)s has a non-numeric score.",
        "zh": "%(path)s 第 %(line)s 行有非数字得分。",
    },
    "pca_width": {
        "en": "%(path)s line %(line)s has %(got)s score columns, expected %(want)s.",
        "zh": "%(path)s 第 %(line)s 行有 %(got)s 个得分列，应为 %(want)s。",
    },
    "pca_dup": {
        "en": "%(path)s has a duplicate IID %(iid)s.",
        "zh": "%(path)s 的 IID %(iid)s 重复。",
    },
    "pca_missing": {
        "en": "%(path)s has no row for id %(iid)s.",
        "zh": "%(path)s 没有 id %(iid)s 的行。",
    },
    "pca_n_range": {
        "en": "--pca-n must be from 1 to %(have)s score columns, got %(n)s.",
        "zh": "--pca-n 必须在 1 到 %(have)s 个得分列之间，收到 %(n)s。",
    },
    "hclust_fewer": {
        "en": "Hierarchical clustering returned %(got)s groups, not %(want)s. fcluster with criterion maxclust returns fewer groups when equal merge distances are cut together.",
        "zh": "层次聚类得到 %(got)s 组，不是 %(want)s。合并距离相同时，fcluster 的 maxclust 会一次切开，组数更少。",
    },
    "kmeans_all_failed": {
        "en": "kmeans2 had no successful restart in %(restarts)s (empty clusters count as failed restarts; %(failed)s failed).",
        "zh": "kmeans2 在 %(restarts)s 次重启里没有成功（空簇算失败；失败 %(failed)s 次）。",
    },
    "hclust_pre_ignored": {
        "en": "Warning: --hclust-pre is not used by --auto-groups hclust. The tree uses every row.",
        "zh": "注意：--auto-groups hclust 不使用 --hclust-pre。树使用全部行。",
    },
    "auto_groups_ids": {
        "en": "auto_groups needs one id per row, got %(ids)s ids and %(rows)s rows.",
        "zh": "auto_groups 需要每行一个 id，收到 %(ids)s 个 id 和 %(rows)s 行。",
    },
    "auto_groups_shape": {
        "en": "auto_groups needs a 2-d matrix, got shape %(shape)s.",
        "zh": "auto_groups 需要二维矩阵，收到形状 %(shape)s。",
    },
    "auto_groups_method": {
        "en": "auto_groups method must be major, threshold, hclust, or kmeans, got %(method)s.",
        "zh": "auto_groups 的 method 只能是 major、threshold、hclust 或 kmeans，收到 %(method)s。",
    },
    "auto_pca_shape": {
        "en": "PCA scores have %(rows)s rows, expected %(want)s.",
        "zh": "PCA 得分有 %(rows)s 行，应为 %(want)s。",
    },
    "auto_pca_n_mismatch": {
        "en": "PCA scores have %(got)s columns, expected --pca-n %(n)s.",
        "zh": "PCA 得分有 %(got)s 列，--pca-n 为 %(n)s。",
    },
    "auto_dup_id": {
        "en": "auto_groups ids contain a duplicate %(iid)s.",
        "zh": "auto_groups 的 id %(iid)s 重复。",
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
