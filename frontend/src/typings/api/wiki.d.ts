declare namespace Api {
  /**
   * namespace Wiki
   *
   * 知识库域：目录树 + Markdown 文档（后端 WikiPageSerializer 输出 snake_case 字段，
   * 与 cmdb 资源一致，前端不做驼峰转换）。
   */
  namespace Wiki {
    /** 目录树节点（WikiPageTreeSerializer 输出，不含正文） */
    interface PageNode {
      id: number;
      title: string;
      /** 父节点 id，顶级为 null */
      parent: number | null;
      /** true 表示目录（可挂子节点），false 表示文档 */
      is_folder: boolean;
      sort: number;
      is_active: boolean;
    }

    /** 文档详情（WikiPageSerializer 输出，含 Markdown 正文） */
    interface PageDetail extends PageNode {
      content: string;
      created_at: string | null;
      updated_at: string | null;
      created_by: string | null;
      updated_by: string | null;
    }

    /** 前端树结构（由扁平 PageNode 列表组装） */
    interface TreeNode extends PageNode {
      children: TreeNode[];
    }

    /** 新建 / 更新入参（更新时可只传需要变更的字段） */
    interface PagePayload {
      title?: string;
      parent?: number | null;
      is_folder?: boolean;
      content?: string;
      sort?: number;
    }

    /** 上传接口返回（POST /api/v1/files） */
    interface UploadedFile {
      name: string;
      url: string;
    }
  }
}
